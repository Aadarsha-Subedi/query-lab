import pytest
from django.db import IntegrityError, transaction

from accounts.models import User
from workspaces.context import DEMO, ref_for
from workspaces.models import Workspace

pytestmark = pytest.mark.django_db


def test_names_come_from_the_id(user: User) -> None:
    workspace = Workspace.objects.create(owner=user, name="Sales; DROP TABLE x")
    assert workspace.schema_name == f"ws_{workspace.pk}"
    assert workspace.role_name == f"ws_{workspace.pk}_rw"
    assert workspace.ref == ref_for(workspace.pk)
    assert workspace.status == Workspace.STATUS_CREATING


def test_name_is_unique_per_owner_only(user: User, other_user: User) -> None:
    Workspace.objects.create(owner=user, name="Sales")
    Workspace.objects.create(owner=other_user, name="Sales")
    with pytest.raises(IntegrityError), transaction.atomic():
        Workspace.objects.create(owner=user, name="Sales")


def test_the_demo_is_a_constant_not_a_row() -> None:
    assert DEMO.is_demo and DEMO.schema_name == "demo"
    assert ref_for(None) is DEMO
    assert not ref_for(7).is_demo
