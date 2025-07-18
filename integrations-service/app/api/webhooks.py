"""Webhook handling endpoints."""

from fastapi import APIRouter, HTTPException, status, Request, Header, BackgroundTasks
from typing import Optional, Dict, Any
import logging
import json

from app.services.webhook_service import WebhookService
from app.api.dependencies import get_webhook_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{integration_type}/{integration_id}")
async def handle_webhook(
    integration_type: str,
    integration_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
    x_github_signature: Optional[str] = Header(None),
    x_github_signature_256: Optional[str] = Header(None),
    service: WebhookService = Depends(get_webhook_service),
):
    """Handle incoming webhooks from integrations."""
    # Get request body
    body = await request.body()
    
    # Get headers for signature verification
    headers = dict(request.headers)
    
    # Determine signature based on integration type
    signature = None
    event_type = None
    
    if integration_type == "hubspot":
        signature = x_hub_signature_256 or x_hub_signature
        # HubSpot sends event type in payload
    elif integration_type == "github":
        signature = x_github_signature_256 or x_github_signature
        event_type = x_github_event
    elif integration_type == "salesforce":
        # Salesforce uses different signature method
        signature = headers.get("x-sfdc-signature")
    elif integration_type == "wordpress":
        # WordPress signature varies by plugin
        signature = headers.get("x-wp-signature")
    
    # Verify webhook signature
    try:
        is_valid = await service.verify_webhook(
            integration_type=integration_type,
            integration_id=integration_id,
            signature=signature,
            body=body,
        )
        
        if not is_valid:
            logger.warning(f"Invalid webhook signature for {integration_type}/{integration_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
    except Exception as e:
        logger.error(f"Webhook verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook verification failed"
        )
    
    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Extract event type from payload if not in headers
    if not event_type:
        if integration_type == "hubspot":
            # HubSpot sends array of events
            if isinstance(payload, list) and payload:
                event_type = payload[0].get("subscriptionType")
        elif integration_type == "salesforce":
            event_type = payload.get("event", {}).get("type")
        elif integration_type == "wordpress":
            event_type = payload.get("action")
    
    # Process webhook asynchronously
    background_tasks.add_task(
        service.process_webhook,
        integration_type=integration_type,
        integration_id=integration_id,
        event_type=event_type,
        payload=payload,
        headers=headers,
    )
    
    # Return immediate response
    return {"status": "accepted", "message": "Webhook received and queued for processing"}


@router.get("/{integration_type}/setup")
async def get_webhook_setup_info(
    integration_type: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """Get webhook setup information for an integration type."""
    setup_info = await service.get_webhook_setup_info(integration_type)
    
    if not setup_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration type {integration_type} not found"
        )
    
    return setup_info


@router.post("/{integration_id}/register")
async def register_webhooks(
    integration_id: str,
    events: list[str],
    service: WebhookService = Depends(get_webhook_service),
):
    """Register webhooks for an integration."""
    try:
        result = await service.register_webhooks(integration_id, events)
        return {
            "status": "success",
            "registered_events": result["events"],
            "webhook_url": result["webhook_url"],
        }
    except Exception as e:
        logger.error(f"Failed to register webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to register webhooks: {str(e)}"
        )


@router.delete("/{integration_id}/unregister")
async def unregister_webhooks(
    integration_id: str,
    service: WebhookService = Depends(get_webhook_service),
):
    """Unregister all webhooks for an integration."""
    try:
        await service.unregister_webhooks(integration_id)
        return {"status": "success", "message": "Webhooks unregistered"}
    except Exception as e:
        logger.error(f"Failed to unregister webhooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to unregister webhooks: {str(e)}"
        )