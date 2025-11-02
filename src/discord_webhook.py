"""
Discord Webhook Integration for FM Reloaded Mod Manager
Handles sending error reports and mod submissions to Discord channels.
"""

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import base64


class DiscordWebhook:
    """Interface to send messages and files to Discord via webhooks."""

    def __init__(self, webhook_url: str):
        """
        Initialize Discord webhook.

        Args:
            webhook_url: Discord webhook URL for the channel
        """
        self.webhook_url = webhook_url

    def send_message(
        self,
        content: str = "",
        embeds: Optional[List[Dict]] = None,
        username: Optional[str] = None,
        thread_name: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> bool:
        """
        Send a text message to Discord.

        Args:
            content: Message content (up to 2000 characters)
            embeds: List of embed dictionaries (rich formatting)
            username: Override webhook username
            thread_name: Optional name to create a thread (threads-enabled channels only)
            thread_id: Optional id of an existing thread

        Returns:
            True if successful, False otherwise
        """
        payload = {}

        if content:
            payload['content'] = content[:2000]  # Discord limit

        if embeds:
            payload['embeds'] = embeds

        if username:
            payload['username'] = username
        if thread_name:
            payload['thread_name'] = thread_name

        custom_url = self.webhook_url
        if thread_id:
            separator = '&' if '?' in custom_url else '?'
            custom_url = f"{custom_url}{separator}thread_id={thread_id}"

        return self._send_payload(payload, webhook_override=custom_url)

    def send_error_report(
        self,
        user_description: str,
        log_files: List[Path],
        app_version: str = "Unknown",
        user_email: Optional[str] = None
    ) -> bool:
        """
        Send an error report with log files attached.

        Args:
            user_description: User's description of the error
            log_files: List of log file paths to attach
            app_version: Application version
            user_email: Optional user contact email

        Returns:
            True if successful
        """
        # Create embed with error details
        embed = {
            "title": "Bug Report",
            "description": user_description[:2048],
            "color": 15158332,  # Red color
            "fields": [
                {
                    "name": "App Version",
                    "value": app_version,
                    "inline": True
                },
                {
                    "name": "Timestamp",
                    "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": True
                }
            ],
            "footer": {
                "text": "FM Reloaded Mod Manager - Error Report"
            }
        }

        if user_email:
            embed['fields'].append({
                "name": "Contact",
                "value": user_email,
                "inline": False
            })

        # Add log file names to embed
        if log_files:
            log_names = [f.name for f in log_files if f.exists()]
            if log_names:
                embed['fields'].append({
                    "name": "Attached Logs",
                    "value": "\n".join(f"• {name}" for name in log_names[:10]),
                    "inline": False
                })

        # Send message with embed
        payload = {
            "embeds": [embed],
            "username": "FM Reloaded Bug Reporter"
        }

        # For now, send without file attachments (Discord webhooks have limitations)
        # Files would require multipart/form-data which is complex without requests library
        thread_name = f"Error {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        payload['thread_name'] = thread_name
        success = self._send_payload(payload)

        if success and log_files:
            # Send log content as code blocks (fallback method)
            self._send_log_contents(log_files)

        return success

    def send_mod_submission(
        self,
        github_repo_url: str,
        mod_name: str,
        mod_author: str,
        mod_description: str,
        mod_type: str,
        submitter_contact: Optional[str] = None
    ) -> bool:
        """
        Send a mod submission request to the ADD-MOD channel.

        Args:
            github_repo_url: GitHub repository URL
            mod_name: Name of the mod
            mod_author: Mod author name
            mod_description: Brief description
            mod_type: Mod type (ui, graphics, tactics, etc.)
            submitter_contact: Optional contact info

        Returns:
            True if successful
        """
        embed = {
            "title": f"New Mod Submission: {mod_name}",
            "description": mod_description[:2048],
            "color": 5763719,  # Green color
            "fields": [
                {
                    "name": "GitHub Repository",
                    "value": f"[{github_repo_url}]({github_repo_url})",
                    "inline": False
                },
                {
                    "name": "Author",
                    "value": mod_author,
                    "inline": True
                },
                {
                    "name": "Type",
                    "value": mod_type,
                    "inline": True
                },
                {
                    "name": "Submitted",
                    "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": True
                }
            ],
            "footer": {
                "text": "FM Reloaded Mod Manager - Mod Submission"
            }
        }

        if submitter_contact:
            embed['fields'].append({
                "name": "Submitter Contact",
                "value": submitter_contact,
                "inline": False
            })

        payload = {
            "embeds": [embed],
            "username": "FM Reloaded Mod Submitter"
        }

        return self._send_payload(payload)

    def _send_payload(self, payload: Dict, webhook_override: Optional[str] = None) -> bool:
        """
        Send JSON payload to Discord webhook.

        Args:
            payload: Dictionary to send as JSON

        Returns:
            True if successful
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'FM-Reloaded-Mod-Manager/1.0'
            }

            data = json.dumps(payload).encode('utf-8')
            request = urllib.request.Request(
                webhook_override or self.webhook_url,
                data=data,
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status == 204  # Discord returns 204 No Content on success

        except urllib.error.HTTPError as e:
            print(f"Discord webhook HTTP error: {e.code} - {e.reason}")
            if e.code == 400:
                print(f"Response: {e.read().decode('utf-8')}")
            return False
        except urllib.error.URLError as e:
            print(f"Discord webhook connection error: {e}")
            return False
        except Exception as e:
            print(f"Discord webhook error: {e}")
            return False

    def _send_log_contents(self, log_files: List[Path], max_size_kb: int = 100) -> None:
        """
        Send log file contents as code blocks.

        Args:
            log_files: List of log files to send
            max_size_kb: Maximum size per file in KB
        """
        for log_file in log_files[:3]:  # Limit to 3 files
            if not log_file.exists():
                continue

            try:
                # Check file size
                size_kb = log_file.stat().st_size / 1024
                if size_kb > max_size_kb:
                    # Send truncated version
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        # Get last N lines
                        last_lines = lines[-100:] if len(lines) > 100 else lines
                        content = ''.join(last_lines)
                        truncated_msg = f"(Showing last 100 lines of {len(lines)} total)"
                else:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        truncated_msg = ""

                # Send as code block (Discord markdown)
                code_block = f"```\n{log_file.name} {truncated_msg}\n{content[:1800]}\n```"
                self.send_message(content=code_block)

            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")


class DiscordChannels:
    """Manage multiple Discord webhook channels."""

    def __init__(self, error_webhook_url: str = "", mod_submission_webhook_url: str = ""):
        """
        Initialize Discord channel webhooks.

        Args:
            error_webhook_url: Webhook URL for ERROR-REPORT channel
            mod_submission_webhook_url: Webhook URL for ADD-MOD channel
        """
        self.error_channel = DiscordWebhook(error_webhook_url) if error_webhook_url else None
        self.mod_channel = DiscordWebhook(mod_submission_webhook_url) if mod_submission_webhook_url else None

    def report_error(
        self,
        description: str,
        log_files: List[Path],
        app_version: str = "Unknown",
        user_email: Optional[str] = None
    ) -> bool:
        """Send error report to ERROR-REPORT channel."""
        if not self.error_channel:
            print("Error webhook not configured")
            return False

        return self.error_channel.send_error_report(
            user_description=description,
            log_files=log_files,
            app_version=app_version,
            user_email=user_email
        )

    def submit_mod(
        self,
        github_url: str,
        mod_name: str,
        author: str,
        description: str,
        mod_type: str,
        contact: Optional[str] = None
    ) -> bool:
        """Send mod submission to ADD-MOD channel."""
        if not self.mod_channel:
            print("Mod submission webhook not configured")
            return False

        return self.mod_channel.send_mod_submission(
            github_repo_url=github_url,
            mod_name=mod_name,
            mod_author=author,
            mod_description=description,
            mod_type=mod_type,
            submitter_contact=contact
        )

    def set_error_webhook(self, url: str) -> None:
        """Update error reporting webhook URL."""
        self.error_channel = DiscordWebhook(url)

    def set_mod_webhook(self, url: str) -> None:
        """Update mod submission webhook URL."""
        self.mod_channel = DiscordWebhook(url)


# Module-level convenience instance (to be configured by GUI)
_discord_channels: Optional[DiscordChannels] = None


def initialize_discord(error_webhook: str = "", mod_webhook: str = "") -> DiscordChannels:
    """
    Initialize global Discord channels instance.

    Args:
        error_webhook: ERROR-REPORT channel webhook URL
        mod_webhook: ADD-MOD channel webhook URL

    Returns:
        DiscordChannels instance
    """
    global _discord_channels
    _discord_channels = DiscordChannels(error_webhook, mod_webhook)
    return _discord_channels


def get_discord_channels() -> Optional[DiscordChannels]:
    """Get the global Discord channels instance."""
    return _discord_channels
