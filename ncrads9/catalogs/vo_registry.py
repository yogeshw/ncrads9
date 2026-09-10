# NCRADS9 - NCRA DS9-like FITS Viewer
# Copyright (C) 2026 Yogesh Wadadekar
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
The VO registry: finding services, then querying the one you found.

DS9's VO menu lists a handful of services it knows about. This asks the
registry instead, so a service that did not exist when this was written can
still be used -- which is the point of there being a registry.

Four service kinds, and they answer different questions:

  - `conesearch` returns catalogue rows around a position;
  - `sia` returns images;
  - `ssa` returns spectra;
  - `tap` answers ADQL, which is a different shape of request and is
    offered here as a discovery result rather than as a query, since a TAP
    query needs a query language and a schema browser to write one.

The registry query is TAP against the RegTAP relational registry, which is
the current way of asking; `astroquery.vo_conesearch`'s directory is
retired. Both the discovery and the service query take an injectable
transport, so neither has to be exercised over the network.

Author: Yogesh Wadadekar
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlencode

from astropy.table import Table

#: The RegTAP endpoint at CDS, the usual mirror.
REGISTRY_URL = "https://reg.g-vo.org/tap/sync"

#: How long to wait, in seconds.
DEFAULT_TIMEOUT = 60.0

#: How many services a discovery accepts.
MAX_SERVICES = 500


class ServiceKind(Enum):
    """The service kinds this can discover."""

    CONE_SEARCH = "conesearch"
    SIA = "sia"
    SSA = "ssa"
    TAP = "tap"

    @property
    def standard_id(self) -> str:
        """The IVOA standard identifier the registry knows it by."""
        return {
            "conesearch": "ivo://ivoa.net/std/conesearch",
            "sia": "ivo://ivoa.net/std/sia",
            "ssa": "ivo://ivoa.net/std/ssa",
            "tap": "ivo://ivoa.net/std/tap",
        }[self.value]

    @property
    def label(self) -> str:
        """What a menu calls it."""
        return {
            "conesearch": "Cone Search",
            "sia": "Simple Image Access",
            "ssa": "Simple Spectral Access",
            "tap": "Table Access Protocol",
        }[self.value]


class RegistryError(RuntimeError):
    """A registry query that failed, for the reason given."""


@dataclass(frozen=True)
class Service:
    """One service the registry described.

    Attributes:
        identifier: Its IVOA identifier.
        title: Its name.
        kind: Which protocol it speaks.
        url: Its access URL.
        publisher: Who runs it.
        description: What it holds.
    """

    identifier: str
    title: str
    kind: ServiceKind
    url: str
    publisher: str = ""
    description: str = ""


#: A fetcher: called with (url, body, timeout) and returning the reply. The
#: body is empty for a GET.
Fetcher = Callable[[str, str, float], str]


def fetch(url: str, body: str = "", timeout: float = DEFAULT_TIMEOUT) -> str:
    """Retrieve a URL, posting `body` if there is one.

    The only function here that uses the network.

    Raises:
        RegistryError: If the request fails.
    """
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    if not url.lower().startswith(("http://", "https://")):
        raise RegistryError(f"not an http URL: {url}")

    request = Request(url, data=body.encode("utf-8") if body else None)
    if body:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (URLError, OSError, ValueError) as exc:
        raise RegistryError(f"could not reach the registry: {exc}") from exc


def discovery_query(kind: ServiceKind, words: str = "", limit: int = MAX_SERVICES) -> str:
    """The ADQL that finds services of one kind.

    Args:
        kind: Which protocol.
        words: Free text to match against the title and description.
        limit: How many to accept.

    Returns:
        The ADQL query.
    """
    # RegTAP's own recommended shape: join the capability and interface
    # tables and filter on the standard id.
    where = [f"rr.capability.standard_id = '{kind.standard_id}'", "rr.interface.intf_role = 'std'"]
    if words.strip():
        # `ivo_hasword` is RegTAP's full-text match; a plain LIKE would
        # miss a description that words the same thing differently.
        safe = words.strip().replace("'", "''")
        where.append(
            f"(1 = ivo_hasword(rr.resource.res_title, '{safe}')"
            f" OR 1 = ivo_hasword(rr.resource.res_description, '{safe}'))"
        )

    return (
        f"SELECT TOP {int(limit)} rr.resource.ivoid, rr.resource.res_title, "
        "rr.resource.res_description, rr.interface.access_url, rr.res_role.role_name "
        "FROM rr.capability "
        "NATURAL JOIN rr.resource "
        "NATURAL JOIN rr.interface "
        "LEFT OUTER JOIN rr.res_role ON (rr.resource.ivoid = rr.res_role.ivoid "
        "AND rr.res_role.base_role = 'publisher') "
        f"WHERE {' AND '.join(where)}"
    )


def discovery_body(kind: ServiceKind, words: str = "", limit: int = MAX_SERVICES) -> str:
    """The POST body for a discovery query."""
    return urlencode(
        {
            "REQUEST": "doQuery",
            "LANG": "ADQL",
            "FORMAT": "votable",
            "QUERY": discovery_query(kind, words, limit),
        }
    )


@dataclass
class DiscoveryResult:
    """What a discovery found.

    Attributes:
        services: The services, in the order returned.
        message: What to tell the user.
    """

    services: list[Service] = field(default_factory=list)
    message: str = ""

    def __bool__(self) -> bool:
        return bool(self.services)


def discover(
    kind: ServiceKind,
    words: str = "",
    fetcher: Fetcher | None = None,
    registry: str = REGISTRY_URL,
    limit: int = MAX_SERVICES,
) -> DiscoveryResult:
    """Ask the registry which services of one kind exist.

    Returns:
        The result. A failure comes back as a message, as elsewhere.
    """
    caller = fetcher or fetch
    try:
        text = caller(registry, discovery_body(kind, words, limit), DEFAULT_TIMEOUT)
    except RegistryError as exc:
        return DiscoveryResult(message=str(exc))
    except Exception as exc:
        return DiscoveryResult(message=f"could not reach the registry: {exc}")

    try:
        table = _parse(text)
    except Exception as exc:
        return DiscoveryResult(message=f"could not read the registry's reply: {exc}")

    if table is None or not len(table):
        return DiscoveryResult(message=f"No {kind.label} services found")

    services = _services(table, kind)
    return DiscoveryResult(services=services, message=f"{len(services)} {kind.label} services")


def _parse(text: str) -> Table | None:
    """Read a VOTable reply."""
    import io

    from astropy.io.votable import parse as parse_votable

    votable = parse_votable(io.BytesIO(text.encode("utf-8")))
    for table in votable.iter_tables():
        if table.array is not None and len(table.array):
            return table.to_table(use_names_over_ids=True)
    return None


def _services(table: Table, kind: ServiceKind) -> list[Service]:
    """Turn a registry reply into services.

    The column names vary between registry mirrors and RegTAP versions, so
    each field is looked up among its known spellings rather than by one
    fixed name.
    """
    lookup = {name.lower(): name for name in table.colnames}

    def column(*candidates: str) -> str | None:
        return next((lookup[key] for key in candidates if key in lookup), None)

    identifier = column("ivoid", "identifier", "id")
    title = column("res_title", "title", "short_name")
    url = column("access_url", "accessurl", "url")
    publisher = column("role_name", "publisher")
    description = column("res_description", "description")

    if url is None:
        return []

    found: list[Service] = []
    seen: set[str] = set()
    for row in table:
        access = str(row[url]).strip()
        if not access or access in seen:
            # One resource can register several interfaces; the first is
            # the one to use, and listing the rest is noise.
            continue
        seen.add(access)
        found.append(
            Service(
                identifier=str(row[identifier]).strip() if identifier else "",
                title=str(row[title]).strip() if title else access,
                kind=kind,
                url=access,
                publisher=str(row[publisher]).strip() if publisher else "",
                description=str(row[description]).strip() if description else "",
            )
        )
    return found


# -- querying a service that was found ----------------------------------------------


def service_query_url(service: Service, longitude: float, latitude: float, radius: float) -> str:
    """The URL that asks one discovered service about a position.

    Args:
        service: The service.
        longitude, latitude: Where, in degrees.
        radius: How far, in degrees.

    Returns:
        The URL.

    Raises:
        RegistryError: For a TAP service, which needs a query rather than a
            position -- offering a cone search to one would be a request it
            cannot answer.
    """
    if service.kind is ServiceKind.TAP:
        raise RegistryError(f"{service.title} is a TAP service: it answers ADQL queries, not cone searches")

    separator = "&" if "?" in service.url else "?"
    if service.kind is ServiceKind.CONE_SEARCH:
        parameters = [("RA", f"{longitude:g}"), ("DEC", f"{latitude:g}"), ("SR", f"{radius:g}")]
    else:
        # SIA and SSA both take POS and SIZE.
        parameters = [
            ("POS", f"{longitude:g},{latitude:g}"),
            ("SIZE", f"{radius:g}"),
            ("FORMAT", "all"),
        ]
    return f"{service.url}{separator}{urlencode(parameters)}"


def query_service(
    service: Service,
    longitude: float,
    latitude: float,
    radius: float,
    fetcher: Fetcher | None = None,
) -> tuple[Table | None, str]:
    """Ask one discovered service about a position.

    Returns:
        The rows and a message. The table is None when nothing came back.
    """
    try:
        url = service_query_url(service, longitude, latitude, radius)
    except RegistryError as exc:
        return (None, str(exc))

    caller = fetcher or fetch
    try:
        text = caller(url, "", DEFAULT_TIMEOUT)
    except RegistryError as exc:
        return (None, str(exc))
    except Exception as exc:
        return (None, f"could not reach {service.title}: {exc}")

    try:
        table = _parse(text)
    except Exception as exc:
        return (None, f"{service.title} sent something unreadable: {exc}")

    if table is None or not len(table):
        return (None, f"{service.title}: nothing found")
    return (table, f"{service.title}: {len(table)} rows")
