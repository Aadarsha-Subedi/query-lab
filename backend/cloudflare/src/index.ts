import { Container } from "@cloudflare/containers";

import secretsTemplate from "../secrets.example.json";
import settings from "../settings.json";

/**
 * Querylab reads more settings than a Worker may have variables (128), so only the real secrets
 * are Worker secrets (`wrangler secret bulk secrets.json`). Their names come from the committed
 * template. Everything else is in settings.json, committed and bundled into the Worker.
 */
const SECRET_NAMES = Object.keys(secretsTemplate);

interface Env {
	BACKEND: DurableObjectNamespace<BackendContainer>;
	[secret: string]: unknown;
}

/** The value in secrets.example.json: it means "someone forgot to fill this in". */
const PLACEHOLDER = "FILL_ME";

/**
 * Same rule as settings/base.py: a missing variable is an error. A value that still holds the
 * placeholder is an error too; the message names the variables, never their values.
 */
function containerEnv(env: Env): Record<string, string> {
	const result: Record<string, string> = { ...settings };
	const missing: string[] = [];
	const placeholders: string[] = [];
	for (const name of SECRET_NAMES) {
		const value = env[name];
		if (typeof value !== "string") {
			missing.push(name);
			continue;
		}
		if (value.includes(PLACEHOLDER)) {
			placeholders.push(name);
		}
		result[name] = value;
	}
	if (missing.length > 0) {
		throw new SettingsError(`Missing secret(s): ${missing.join(", ")}`);
	}
	if (placeholders.length > 0) {
		throw new SettingsError(`Placeholder value left in: ${placeholders.join(", ")}`);
	}
	return result;
}

class SettingsError extends Error {}

const IDLE_MS = 3 * 60 * 1000;

/** The Django container. It sleeps when idle and starts again on the next request. */
export class BackendContainer extends Container<Env> {
	defaultPort = 8080;
	sleepAfter = "3m";

	private lastRequestAt = Date.now();

	override async fetch(request: Request): Promise<Response> {
		this.lastRequestAt = Date.now();
		return super.fetch(request);
	}

	/**
	 * `sleepAfter` alone never fires once a client drops a request mid-way: the library
	 * then counts it as open forever (cloudflare/containers#241, #242).
	 */
	override async alarm(alarmProps?: AlarmInvocationInfo): Promise<void> {
		if (this.ctx.container?.running && Date.now() - this.lastRequestAt >= IDLE_MS) {
			await this.stop();
		}
		return super.alarm(alarmProps);
	}

	/**
	 * Called by the Worker on every request with the settings it sees right now. A running
	 * container keeps the environment it started with, and this object can outlive a
	 * secret change, so compare a fingerprint of the settings with the one the container
	 * was started with and restart it when they differ. Only the hash is stored.
	 */
	async syncSettings(settings: Record<string, string>): Promise<void> {
		const fingerprint = await settingsFingerprint(settings);
		this.envVars = settings;
		if ((await this.ctx.storage.get<string>(FINGERPRINT_KEY)) !== fingerprint) {
			if (this.ctx.container?.running) await this.stop();
			await this.ctx.storage.put(FINGERPRINT_KEY, fingerprint);
		}
	}
}

const FINGERPRINT_KEY = "settings-fingerprint";

/** SHA-256 of the settings, so the values themselves are never stored. */
async function settingsFingerprint(settings: Record<string, string>): Promise<string> {
	const text = JSON.stringify(Object.entries(settings).sort(([a], [b]) => a.localeCompare(b)));
	const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
	return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		// Tell Django the original scheme and client address (it sees only this Worker)
		const headers = new Headers(request.headers);
		headers.set("X-Forwarded-Proto", "https");
		const clientIp = request.headers.get("CF-Connecting-IP");
		if (clientIp) headers.set("X-Forwarded-For", clientIp);

		const backend = env.BACKEND.getByName("backend");
		try {
			await backend.syncSettings(containerEnv(env));
		} catch (error) {
			if (error instanceof SettingsError) {
				return new Response(error.message, { status: 500 });
			}
			throw error;
		}
		return backend.fetch(new Request(request, { headers }));
	},
} satisfies ExportedHandler<Env>;
