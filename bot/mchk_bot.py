# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "discord-py",
#     "gitpython",
# ]
# ///
"""
uv run bot/mchk_bot.py \
    --token ? \
    --channel-id ? \
    --repo-path "." \
    --wod-path "wods" \
    --site-content-path "site/contents/wods"
"""

import argparse
import datetime
import enum
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import discord
from git import Repo


def log(msg: str):
    print(f"---\n{msg}\n")


class MessageType(enum.StrEnum):
    """Enum to determine the type of messages and what to do with them.

    Only '!!!wod' is available.
    """

    WOD = "!!!wod"


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents, **options):
        self._channel_id = options.pop("channel_id", None)
        self._repo_path = options.pop("channel_id", ".")
        self._wod_path = options.pop("channel_id", "./wods")
        self._site_content_path = options.pop(
            "site_content_path", "./site/content/wods"
        )
        super().__init__(intents=intents, **options)

    async def on_ready(self):
        print(f"Logged in as {client.user}")
        self.loop.create_task(self.fetch_and_exit())  # Schedule exit task

    async def on_message(self, message):
        print(f"Message from {message.author}: {message.content}")

    async def fetch_and_exit(self):
        await self.wait_until_ready()  # Wait for connection

        channel = self.get_channel(self._channel_id)
        log(f"Connected to channel: {channel.name}")

        # Fetch message history
        messages: list[WodMessage] = []
        async for message in channel.history(limit=5):
            if message.content.startswith(MessageType.WOD) and (
                wod_message := await clean_wod_message(
                    message.created_at, message.content
                )
            ):
                messages.append(wod_message)

        messages = sorted(messages, key=lambda x: x.created_at)
        last_message = messages[-1]
        await last_message.create_wod(
            self._repo_path, self._wod_path, self._site_content_path
        )

        log("Done, closing client")
        await self.close()  # Disconnect after completion


@dataclass
class WodMessage:
    """Deals with a message from the discord channel.

    The first line must be the message type, the second one must contain
    the name of the wod and the file date separated by a comma, and from
    the 3rd line onwards the wod must be written as it would be done in
    a wod file.

    Examples:

        Example of a message:

        ```
        !!!wod
        wod-17-03-25,2025-03-17
        wl 3x5 front squat @80%
        wl 4x2 clean @80%
        wl 3x4 push press @80%
        2rd 45cal row, 30 toes to bar, 15 clean and jerk @65/43kg
        ```
    """

    created_at: datetime.datetime
    new_wodfile: str
    file_date: str
    content: str

    @classmethod
    def from_content_lines(
        cls, lines: list[str], created_at: datetime.datetime = datetime.datetime.now()
    ) -> Self:
        new_wodfile, file_date = lines[0].split(",")
        return cls(
            created_at=created_at,
            new_wodfile=new_wodfile,
            file_date=file_date,
            content="\n".join(lines[1:]),
        )

    def get_wod_args(
        self, repo_path: str, wod_path: str, site_path_content: str
    ) -> tuple[str, str, str]:
        return (
            str((Path(repo_path) / site_path_content / self.new_wodfile).resolve()),
            str((Path(repo_path) / wod_path / f"{self.new_wodfile}.wod").resolve()),
            self.file_date,
        )

    async def create_wod(
        self,
        repo_path: str = ".",
        wod_path: str = "wods",
        site_path_content: str = "site/content/wods",
    ):
        (new_filename, wodfile, file_date) = self.get_wod_args(
            repo_path, wod_path, site_path_content
        )
        cmd = [
            "wod",
            new_filename,
            "--wodfile",
            wodfile,
            "--file-date",
            file_date,
            "--languages",
            "en,es",  # Generate english and spanish filenames
        ]
        self.write_wod_file(wodfile)
        result = subprocess.run(cmd, capture_output=True, check=False)
        log(f"CMD:\n{result.args}")
        if err := result.stderr.decode("utf-8"):
            print("Error while running `wod`:\n", err)
            return
        log("`wod` executed succesfully")
        # self.commit_and_push(repo_name)

    def write_wod_file(self, path: Path):
        with open(path, "w") as f:
            f.write(self.content)
        log(f"File written at: {path}")

    async def commit_and_push(self, repo_name: str):
        try:
            repo = Repo(repo_name)

            # Check if there are any changes
            if not repo.is_dirty() and not repo.untracked_files:
                log("No changes to commit")
                return

            # Add all changes
            repo.git.add(all=True)

            # Commit changes
            commit_message = f"Add WOD by bot ({datetime.datetime.now().ctime()})"
            repo.git.commit("-m", commit_message)

            # Push changes
            log("Pushing changes to remote...")
            repo.git.push()

            log("Changes committed and pushed successfully")

        except Exception as e:
            log(f"Error committing and pushing changes: {e}")


async def clean_wod_message(date: datetime.datetime, content: str) -> WodMessage | None:
    """Ensure the message is a wod type, the first line must be only '!!!wod'.

    Args:
        date (datetime.datetime): Date when the message was created.
        content (str): Message body splitted by lines.

    Returns:
        message (WodMessage): Dataclass containing the message, or None
            if it's not the expected type of message.
    """
    lines = content.splitlines()
    if lines[0] == MessageType.WOD:
        return WodMessage.from_content_lines(lines[1:], created_at=date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discord WOD Bot")
    parser.add_argument("--token", required=True, help="Discord bot token")
    parser.add_argument(
        "--channel-id", required=True, help="Discord channel ID to monitor"
    )
    parser.add_argument("--repo-path", required=True, help="Path to the git repository")
    parser.add_argument(
        "--wod-path", required=True, help="Path where .wod files should be stored"
    )
    parser.add_argument(
        "--site-content-path",
        required=True,
        help="Path where site content files should be stored",
    )

    args = parser.parse_args()

    intents = discord.Intents.default()
    intents.message_content = True  # Required to read message content
    intents.guilds = True
    intents.messages = True
    intents.members = True  # Add this to see all members

    client = MyClient(intents=intents, channel_id=int(args.channel_id))

    client.run(args.token)
