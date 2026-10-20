import datetime as dt
import time
import uuid

import httpx

from app.application.ports import (
    HoldConflict,
    HoldExpired,
    HoldNotFound,
    NoInventory,
    PaymentInfo,
    PaymentNotFound,
    RoomInfo,
)
from app.domain.errors import DependencyUnavailable, InvalidState, RoomNotFound
from app.logging import current_request_id

GET_RETRIES = 3


def _code(response: httpx.Response) -> str | None:
    try:
        return response.json().get("error", {}).get("code")
    except ValueError:
        return None


def _unavailable(response: httpx.Response) -> DependencyUnavailable:
    return DependencyUnavailable(
        f"{response.request.method} {response.request.url.path} -> {response.status_code}",
        ambiguous=response.status_code >= 500,
    )


class HttpJson:
    def __init__(
        self,
        base_url: str,
        connect_timeout: float,
        read_timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.client = httpx.Client(
            base_url=base_url,
            transport=transport,
            timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
        )

    def close(self) -> None:
        self.client.close()

    def _request(
        self, method: str, path: str, headers: dict | None = None, **kwargs
    ) -> httpx.Response:
        merged = {"X-Request-ID": current_request_id()}
        if headers:
            merged.update(headers)
        try:
            return self.client.request(method, path, headers=merged, **kwargs)
        except httpx.ConnectError as e:
            raise DependencyUnavailable(str(e), ambiguous=False) from e
        except httpx.HTTPError as e:
            raise DependencyUnavailable(str(e), ambiguous=True) from e

    def get(self, path: str, params: dict | None = None) -> httpx.Response:
        last: DependencyUnavailable | None = None
        for attempt in range(GET_RETRIES):
            try:
                response = self._request("GET", path, params=params)
            except DependencyUnavailable as e:
                last = e
            else:
                if response.status_code < 500:
                    return response
                last = _unavailable(response)
            if attempt < GET_RETRIES - 1:
                time.sleep(0.05 * (2**attempt))
        if last is None:
            raise DependencyUnavailable("sin respuesta válida", ambiguous=True)
        raise last

    def post(
        self, path: str, json: dict | None = None, headers: dict | None = None
    ) -> httpx.Response:
        return self._request("POST", path, json=json, headers=headers)


class HttpAvailabilityClient:
    def __init__(self, http: HttpJson) -> None:
        self.http = http

    def create_hold(
        self,
        hold_id: uuid.UUID,
        room_id: uuid.UUID,
        check_in: dt.date,
        check_out: dt.date,
        units: int,
        ttl_seconds: int,
    ) -> str:
        response = self.http.post(
            "/holds",
            json={
                "hold_id": str(hold_id),
                "room_id": str(room_id),
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "units": units,
                "ttl_seconds": ttl_seconds,
            },
        )
        if response.status_code in (200, 201):
            return response.json()["status"]
        if response.status_code == 409:
            code = _code(response)
            if code == "NO_INVENTORY":
                raise NoInventory()
            if code == "HOLD_CONFLICT":
                raise HoldConflict()
        raise _unavailable(response)

    def extend_hold(self, hold_id: uuid.UUID, ttl_seconds: int) -> dt.datetime:
        response = self.http.post(
            f"/holds/{hold_id}/extend", json={"ttl_seconds": ttl_seconds}
        )
        if response.status_code == 200:
            return dt.datetime.fromisoformat(response.json()["expires_at"])
        if response.status_code == 409 and _code(response) == "HOLD_EXPIRED":
            raise HoldExpired()
        if response.status_code == 404:
            raise HoldNotFound()
        raise _unavailable(response)

    def confirm_hold(self, hold_id: uuid.UUID) -> str:
        response = self.http.post(f"/holds/{hold_id}/confirm")
        if response.status_code == 200:
            return response.json()["status"]
        if response.status_code == 409 and _code(response) == "HOLD_EXPIRED":
            raise HoldExpired()
        if response.status_code == 404:
            raise HoldNotFound()
        raise _unavailable(response)

    def release_hold(self, hold_id: uuid.UUID) -> str:
        response = self.http.post(f"/holds/{hold_id}/release")
        if response.status_code == 200:
            return response.json()["status"]
        if response.status_code == 404:
            raise HoldNotFound()
        raise _unavailable(response)


class HttpPaymentClient:
    def __init__(self, http: HttpJson) -> None:
        self.http = http

    def create(
        self,
        reservation_id: uuid.UUID,
        amount_cents: int,
        currency: str,
        method: str,
        token: str,
        simulate: str,
    ) -> PaymentInfo:
        response = self.http.post(
            "/payments",
            headers={"Idempotency-Key": str(reservation_id)},
            json={
                "reservation_id": str(reservation_id),
                "amount_cents": amount_cents,
                "currency": currency,
                "method": method,
                "token": token,
                "simulate": simulate,
            },
        )
        if response.status_code in (200, 201):
            body = response.json()
            return PaymentInfo(id=uuid.UUID(body["id"]), status=body["status"])
        raise _unavailable(response)

    def get_by_reservation(self, reservation_id: uuid.UUID) -> PaymentInfo:
        response = self.http.get(
            "/payments", params={"reservation_id": str(reservation_id)}
        )
        if response.status_code == 200:
            body = response.json()
            return PaymentInfo(id=uuid.UUID(body["id"]), status=body["status"])
        if response.status_code == 404:
            raise PaymentNotFound()
        raise _unavailable(response)

    def refund(self, payment_id: uuid.UUID) -> PaymentInfo:
        response = self.http.post(f"/payments/{payment_id}/refund")
        if response.status_code == 200:
            return PaymentInfo(id=payment_id, status=response.json()["status"])
        if response.status_code == 404:
            raise PaymentNotFound()
        if response.status_code == 409:
            raise InvalidState("no se puede reembolsar")
        raise _unavailable(response)


class HttpCustomerClient:
    def __init__(self, http: HttpJson) -> None:
        self.http = http

    def exists(self, customer_id: uuid.UUID) -> bool:
        response = self.http.get(f"/customers/{customer_id}")
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        raise _unavailable(response)


class HttpHotelClient:
    def __init__(self, http: HttpJson) -> None:
        self.http = http

    def get_room(self, room_id: uuid.UUID) -> RoomInfo:
        response = self.http.get(f"/rooms/{room_id}")
        if response.status_code == 200:
            body = response.json()
            return RoomInfo(
                hotel_id=uuid.UUID(body["hotel_id"]),
                price_cents=body["price_per_night_cents"],
            )
        if response.status_code == 404:
            raise RoomNotFound()
        raise _unavailable(response)
