import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic.networks import EmailStr

from interactem.app.api.deps import CurrentUser, get_current_active_superuser
from interactem.app.models import Message, Pipeline
from interactem.app.utils import generate_test_email, send_email

router = APIRouter()


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


def check_present_and_authorized(
    pipeline: Pipeline | None, current_user: CurrentUser, id: uuid.UUID
) -> Pipeline:
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline
