"""Octo Browser API client for profile discovery and automation start."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

from src.utils.config import config
from src.utils.logger import logger


@dataclass
class OctoProfile:
    uuid: str
    title: str
    tags: List[str]


class OctoClient:
    """Client for interacting with Octo Browser APIs."""

    def __init__(self) -> None:
        self.settings = config.settings
        self.api_token = self.settings.octo_api_token
        # Cloud API base; path for profiles is fixed per docs
        self.cloud_base_url = self.settings.octo_cloud_base_url
        self.local_api_url = self.settings.octo_local_api_url

        if not self.api_token:
            logger.warning("OCTO_API_TOKEN is not set; Octo profile discovery will not work.")

    async def fetch_profiles(self, search: str | None = None) -> Dict[str, OctoProfile]:
        """Fetch profiles from Octo cloud API and return a map title -> profile.

        Titles are normalised to lower case for lookups.
        """
        if not self.api_token:
            return {}

        params = {
            "page_len": 100,
            "page": 0,
            # We request minimal fields; id and title are most important.
            "fields": "title,tags,status",
        }
        if search:
            params["search"] = search

        headers = {
            "X-Octo-Api-Token": self.api_token,
        }

        url = f"{self.cloud_base_url}/profiles"
        logger.info(f"Requesting Octo profiles from {url} (search={search!r})")

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=headers, params=params)

        if resp.status_code != 200:
            logger.error(f"Failed to fetch Octo profiles: {resp.status_code} {resp.text}")
            return {}

        data = resp.json()
        items = data.get("results") or data.get("data") or []
        logger.info(f"Loaded {len(items)} Octo profiles")

        profiles: Dict[str, OctoProfile] = {}
        for item in items:
            uuid = item.get("uuid") or item.get("id")
            title = (item.get("title") or "").strip()
            if not uuid or not title:
                continue
            tags = item.get("tags") or []
            key = title.lower()
            profiles[key] = OctoProfile(uuid=uuid, title=title, tags=tags)

        logger.info(f"Loaded {len(profiles)} Octo profiles into cache")
        return profiles

    async def start_profile_for_playwright(self, profile_uuid: str) -> Optional[str]:
        """Start a local Octo profile for automation and return ws_endpoint."""
        url = f"{self.local_api_url}/api/profiles/start"
        payload = {
            "uuid": profile_uuid,
            "headless": False,
            "debug_port": True,
        }

        logger.info(f"Starting Octo profile {profile_uuid} via {url}")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)

        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            logger.error(f"Failed to start Octo profile: {resp.status_code} {body}")
            return None

        ws_endpoint = resp.json().get("ws_endpoint")
        if not ws_endpoint:
            logger.error("Octo start response did not include ws_endpoint")
            return None

        # When app runs in Docker, Octo returns ws://127.0.0.1:PORT/... (host loopback).
        # Container's 127.0.0.1 is not the host; rewrite to the same host we used for the API.
        try:
            base = urlparse(self.local_api_url.rstrip("/"))
            api_host = base.hostname
            if api_host and api_host not in ("127.0.0.1", "localhost", "::1"):
                parsed = urlparse(ws_endpoint)
                netloc = f"{api_host}:{parsed.port}" if parsed.port else api_host
                ws_endpoint = f"{parsed.scheme}://{netloc}{parsed.path or ''}"
                logger.info(f"Rewrote CDP endpoint host for Docker: {ws_endpoint}")
        except Exception as e:
            logger.warning(f"Could not rewrite ws_endpoint host: {e}")

        # Optional: tunnel CDP through a bridge manager when running in Docker.
        bridge_url = self.settings.octo_cdp_bridge_url
        if bridge_url:
            try:
                parsed_ws = urlparse(ws_endpoint)
                if not parsed_ws.port:
                    logger.error("ws_endpoint has no port; cannot use CDP bridge")
                else:
                    target_port = parsed_ws.port
                    b = urlparse(bridge_url.rstrip("/"))
                    bridge_api = f"{bridge_url.rstrip('/')}/bridge"
                    logger.info(
                        f"Requesting CDP bridge from {bridge_api} for target_port={target_port}"
                    )
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.post(
                            bridge_api, json={"target_port": target_port}
                        )
                    if resp.is_success:
                        data = resp.json()
                        bridge_port = data.get("port")
                        if isinstance(bridge_port, int):
                            netloc = f"{b.hostname}:{bridge_port}" if b.hostname else f"host.docker.internal:{bridge_port}"
                            ws_endpoint = f"{parsed_ws.scheme}://{netloc}{parsed_ws.path or ''}"
                            logger.info(f"Using CDP bridge endpoint: {ws_endpoint}")
                        else:
                            logger.error(f"Invalid bridge response: {data}")
                    else:
                        logger.error(
                            f"CDP bridge manager error {resp.status_code}: {resp.text}"
                        )
            except Exception as e:
                logger.error(f"Error while requesting CDP bridge: {e}")

        logger.info(f"Octo returned ws_endpoint: {ws_endpoint}")
        return ws_endpoint

