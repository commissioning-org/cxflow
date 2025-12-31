"""
Integration examples for the Webhook Engine.

This module provides ready-to-use examples for common webhook scenarios.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Optional

from .engine import WebhookEngine, DeliveryResult, trigger_power_automate_sync
from .config import WebhookEndpoint, POWER_AUTOMATE_WEBHOOK
from .payload import PayloadBuilder, PayloadFormatter


# =============================================================================
# Power Automate Integration
# =============================================================================

class PowerAutomateClient:
    """
    High-level client for Power Automate webhook integration.
    
    Example:
        client = PowerAutomateClient()
        
        # Trigger a flow
        result = await client.trigger("flow_started", {"user": "john"})
        
        # Send structured data
        result = await client.send_form_submission({
            "name": "John Doe",
            "email": "john@example.com",
            "message": "Hello!"
        })
    """
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        **engine_kwargs: Any,
    ):
        self.engine = WebhookEngine(**engine_kwargs)
        
        if webhook_url:
            self.engine.add_endpoint(WebhookEndpoint(
                name="power_automate",
                url=webhook_url,
                method="POST",
            ))
    
    async def trigger(
        self,
        action: str,
        data: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> DeliveryResult:
        """Trigger a Power Automate flow with data."""
        payload = PayloadFormatter.power_automate(data, action)
        if correlation_id:
            payload["correlationId"] = correlation_id
        
        return await self.engine.send("power_automate", payload)
    
    async def send_form_submission(
        self,
        form_data: dict[str, Any],
        form_name: str = "default",
    ) -> DeliveryResult:
        """Send a form submission to Power Automate."""
        return await self.trigger("form_submission", {
            "formName": form_name,
            "submittedAt": datetime.now(timezone.utc).isoformat(),
            "data": form_data,
        })
    
    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        source: str = "webhook_engine",
    ) -> DeliveryResult:
        """Send an alert to Power Automate."""
        return await self.trigger("alert", {
            "title": title,
            "message": message,
            "severity": severity,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    async def send_notification(
        self,
        title: str,
        body: str,
        recipients: Optional[list[str]] = None,
        channel: str = "email",
    ) -> DeliveryResult:
        """Send a notification via Power Automate."""
        return await self.trigger("notification", {
            "title": title,
            "body": body,
            "recipients": recipients or [],
            "channel": channel,
        })
    
    async def sync_data(
        self,
        entity_type: str,
        entity_id: str,
        data: dict[str, Any],
        operation: str = "upsert",
    ) -> DeliveryResult:
        """Sync data to external system via Power Automate."""
        return await self.trigger("data_sync", {
            "entityType": entity_type,
            "entityId": entity_id,
            "operation": operation,
            "data": data,
        })
    
    async def close(self) -> None:
        """Close the client."""
        await self.engine.close()
    
    async def __aenter__(self) -> PowerAutomateClient:
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# Sync versions for convenience
def trigger_power_automate(
    action: str,
    data: dict[str, Any],
) -> DeliveryResult:
    """Trigger Power Automate workflow synchronously."""
    return trigger_power_automate_sync(data, action)


def send_power_automate_alert(
    title: str,
    message: str,
    severity: str = "info",
) -> DeliveryResult:
    """Send an alert to Power Automate synchronously."""
    return trigger_power_automate_sync({
        "title": title,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, "alert")


# =============================================================================
# Slack Integration
# =============================================================================

class SlackWebhook:
    """
    Slack webhook integration.
    
    Example:
        slack = SlackWebhook("https://hooks.slack.com/services/xxx/yyy/zzz")
        await slack.send_message("Hello, Slack!")
        await slack.send_alert("Server Down", "Production server is not responding", "danger")
    """
    
    def __init__(self, webhook_url: str, **engine_kwargs: Any):
        self.engine = WebhookEngine(enable_queue=False, **engine_kwargs)
        self.engine.add_endpoint(WebhookEndpoint(
            name="slack",
            url=webhook_url,
            method="POST",
            headers={"Content-Type": "application/json"},
        ))
    
    async def send_message(
        self,
        text: str,
        channel: Optional[str] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
    ) -> DeliveryResult:
        """Send a simple text message."""
        payload = PayloadFormatter.slack(
            text=text,
            channel=channel,
            username=username,
            icon_emoji=icon_emoji,
        )
        return await self.engine.send("slack", payload)
    
    async def send_alert(
        self,
        title: str,
        message: str,
        color: str = "warning",  # good, warning, danger
        fields: Optional[list[dict]] = None,
    ) -> DeliveryResult:
        """Send an alert with attachment."""
        payload = {
            "text": title,
            "attachments": [{
                "color": color,
                "text": message,
                "fields": fields or [],
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }],
        }
        return await self.engine.send("slack", payload)
    
    async def send_blocks(
        self,
        blocks: list[dict],
        text: str = "",
    ) -> DeliveryResult:
        """Send a message with Block Kit blocks."""
        payload = PayloadFormatter.slack(text=text, blocks=blocks)
        return await self.engine.send("slack", payload)
    
    async def close(self) -> None:
        await self.engine.close()


# =============================================================================
# Discord Integration
# =============================================================================

class DiscordWebhook:
    """
    Discord webhook integration.
    
    Example:
        discord = DiscordWebhook("https://discord.com/api/webhooks/xxx/yyy")
        await discord.send_message("Hello, Discord!")
        await discord.send_embed("Alert", "Something happened", color=0xff0000)
    """
    
    def __init__(self, webhook_url: str, **engine_kwargs: Any):
        self.engine = WebhookEngine(enable_queue=False, **engine_kwargs)
        self.engine.add_endpoint(WebhookEndpoint(
            name="discord",
            url=webhook_url,
            method="POST",
            headers={"Content-Type": "application/json"},
        ))
    
    async def send_message(
        self,
        content: str,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> DeliveryResult:
        """Send a simple message."""
        payload = PayloadFormatter.discord(
            content=content,
            username=username,
            avatar_url=avatar_url,
        )
        return await self.engine.send("discord", payload)
    
    async def send_embed(
        self,
        title: str,
        description: str,
        color: int = 0x5865f2,  # Discord blurple
        fields: Optional[list[dict]] = None,
        footer: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
    ) -> DeliveryResult:
        """Send an embed message."""
        embed: dict[str, Any] = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if fields:
            embed["fields"] = fields
        if footer:
            embed["footer"] = {"text": footer}
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        
        payload = PayloadFormatter.discord(embeds=[embed])
        return await self.engine.send("discord", payload)
    
    async def close(self) -> None:
        await self.engine.close()


# =============================================================================
# Microsoft Teams Integration
# =============================================================================

class TeamsWebhook:
    """
    Microsoft Teams webhook integration.
    
    Example:
        teams = TeamsWebhook("https://outlook.office.com/webhook/xxx")
        await teams.send_message("Hello, Teams!")
        await teams.send_card("Alert", "Something important happened", "0078D7")
    """
    
    def __init__(self, webhook_url: str, **engine_kwargs: Any):
        self.engine = WebhookEngine(enable_queue=False, **engine_kwargs)
        self.engine.add_endpoint(WebhookEndpoint(
            name="teams",
            url=webhook_url,
            method="POST",
            headers={"Content-Type": "application/json"},
        ))
    
    async def send_message(
        self,
        text: str,
        title: Optional[str] = None,
    ) -> DeliveryResult:
        """Send a simple message."""
        payload = PayloadFormatter.teams(
            title=title or "Notification",
            text=text,
        )
        return await self.engine.send("teams", payload)
    
    async def send_card(
        self,
        title: str,
        text: str,
        theme_color: str = "0076D7",
        sections: Optional[list[dict]] = None,
        actions: Optional[list[dict]] = None,
    ) -> DeliveryResult:
        """Send a message card."""
        payload = PayloadFormatter.teams(
            title=title,
            text=text,
            theme_color=theme_color,
            sections=sections,
            actions=actions,
        )
        return await self.engine.send("teams", payload)
    
    async def send_fact_card(
        self,
        title: str,
        facts: dict[str, str],
        text: Optional[str] = None,
    ) -> DeliveryResult:
        """Send a card with key-value facts."""
        sections = [{
            "facts": [{"name": k, "value": v} for k, v in facts.items()],
        }]
        
        return await self.send_card(
            title=title,
            text=text or "",
            sections=sections,
        )
    
    async def close(self) -> None:
        await self.engine.close()


# =============================================================================
# Generic Webhook Integration
# =============================================================================

class GenericWebhook:
    """
    Generic webhook client for any HTTP endpoint.
    
    Example:
        webhook = GenericWebhook("https://api.example.com/webhook")
        await webhook.post({"event": "user_created", "user_id": "123"})
        await webhook.put({"status": "active"})
    """
    
    def __init__(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        auth_type: Optional[str] = None,
        auth_config: Optional[dict[str, Any]] = None,
        **engine_kwargs: Any,
    ):
        self.engine = WebhookEngine(enable_queue=False, **engine_kwargs)
        self.url = url
        self._endpoint = WebhookEndpoint(
            name="generic",
            url=url,
            method="POST",
            headers=headers or {},
            auth_type=auth_type,
            auth_config=auth_config or {},
        )
        self.engine.add_endpoint(self._endpoint)
    
    async def post(
        self,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> DeliveryResult:
        """Send a POST request."""
        return await self.engine.send("generic", payload, headers=headers)
    
    async def put(
        self,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> DeliveryResult:
        """Send a PUT request."""
        # Temporarily update method
        self._endpoint.method = "PUT"
        result = await self.engine.send("generic", payload, headers=headers)
        self._endpoint.method = "POST"
        return result
    
    async def patch(
        self,
        payload: dict[str, Any],
        headers: Optional[dict[str, str]] = None,
    ) -> DeliveryResult:
        """Send a PATCH request."""
        self._endpoint.method = "PATCH"
        result = await self.engine.send("generic", payload, headers=headers)
        self._endpoint.method = "POST"
        return result
    
    async def close(self) -> None:
        await self.engine.close()


# =============================================================================
# Event Bridge Pattern
# =============================================================================

class EventBridge:
    """
    CloudEvents-style event bridge for multiple webhook targets.
    
    Example:
        bridge = EventBridge()
        bridge.add_target("slack", "https://hooks.slack.com/...")
        bridge.add_target("teams", "https://outlook.office.com/webhook/...")
        
        # Publish to all targets
        await bridge.publish("user.created", {"user_id": "123"})
        
        # Publish to specific targets
        await bridge.publish("alert.critical", {"message": "Error"}, targets=["slack"])
    """
    
    def __init__(self, source: str = "event_bridge", **engine_kwargs: Any):
        self.engine = WebhookEngine(**engine_kwargs)
        self.source = source
        self._targets: dict[str, str] = {}
    
    def add_target(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a webhook target."""
        self._targets[name] = url
        self.engine.add_endpoint(WebhookEndpoint(
            name=name,
            url=url,
            method=method,
            headers=headers or {},
        ))
    
    def remove_target(self, name: str) -> bool:
        """Remove a webhook target."""
        if name in self._targets:
            del self._targets[name]
            return self.engine.remove_endpoint(name)
        return False
    
    async def publish(
        self,
        event_type: str,
        data: dict[str, Any],
        subject: Optional[str] = None,
        targets: Optional[list[str]] = None,
    ) -> dict[str, DeliveryResult]:
        """Publish an event to targets."""
        payload = PayloadFormatter.generic_event(
            event_type=event_type,
            data=data,
            source=self.source,
            subject=subject,
        )
        
        target_names = targets or list(self._targets.keys())
        results = {}
        
        tasks = [
            self.engine.send(name, payload)
            for name in target_names
            if name in self._targets
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, resp in zip(target_names, responses):
            if isinstance(resp, Exception):
                results[name] = DeliveryResult(
                    success=False,
                    error=str(resp),
                    endpoint_name=name,
                )
            else:
                results[name] = resp
        
        return results
    
    async def close(self) -> None:
        await self.engine.close()


# =============================================================================
# Usage Examples
# =============================================================================

async def example_power_automate():
    """Example: Send data to Power Automate."""
    async with PowerAutomateClient() as client:
        # Trigger a flow
        result = await client.trigger("test_event", {
            "message": "Hello from Python!",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        print(f"Power Automate: {result.success}")


async def example_multi_channel_alert():
    """Example: Send alert to multiple channels."""
    bridge = EventBridge(source="my_app")
    
    # Add targets (configure with real URLs)
    # bridge.add_target("slack", "https://hooks.slack.com/...")
    # bridge.add_target("teams", "https://outlook.office.com/webhook/...")
    
    # For this example, use Power Automate
    bridge.add_target(
        "power_automate",
        POWER_AUTOMATE_WEBHOOK.url,
    )
    
    # Publish alert
    results = await bridge.publish(
        "alert.critical",
        {
            "title": "Server Down",
            "message": "Production server is not responding",
            "severity": "critical",
        },
    )
    
    for target, result in results.items():
        print(f"{target}: {'✓' if result.success else '✗'}")
    
    await bridge.close()


async def example_batch_processing():
    """Example: Process batch of webhooks."""
    engine = WebhookEngine()
    
    # Generate sample payloads
    payloads = [
        {"event": f"batch_{i}", "index": i}
        for i in range(100)
    ]
    
    # Send batch with concurrency limit
    results = await engine.send_batch(
        "power_automate",
        payloads,
        concurrency=10,
    )
    
    success = sum(1 for r in results if r.success)
    print(f"Batch: {success}/{len(results)} succeeded")
    
    await engine.close()


if __name__ == "__main__":
    # Run examples
    print("Running Power Automate example...")
    asyncio.run(example_power_automate())
