import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.exc import SQLAlchemyError

from .errors import DependencyUnavailable, HotelNotFound, IdConflict

metadata = sa.MetaData()

hotels = sa.Table(
    "hotels",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("city", sa.String(120), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
)

rooms = sa.Table(
    "rooms",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "hotel_id",
        UUID(as_uuid=True),
        sa.ForeignKey("hotels.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("name", sa.String(120), nullable=False),
    sa.Column("capacity", sa.Integer, nullable=False),
    sa.Column("price_per_night_cents", sa.Integer, nullable=False),
    sa.Column("currency", sa.String(3), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.CheckConstraint("capacity BETWEEN 1 AND 10", name="rooms_capacity_check"),
    sa.CheckConstraint("price_per_night_cents > 0", name="rooms_price_check"),
    sa.CheckConstraint("currency = 'USD'", name="rooms_currency_check"),
)

HOTEL_COLUMNS = (hotels.c.id, hotels.c.name, hotels.c.city, hotels.c.created_at)
ROOM_COLUMNS = (
    rooms.c.id,
    rooms.c.hotel_id,
    rooms.c.name,
    rooms.c.capacity,
    rooms.c.price_per_night_cents,
    rooms.c.currency,
    rooms.c.created_at,
)


def _unavailable(exc: Exception) -> DependencyUnavailable:
    return DependencyUnavailable("base de datos no disponible")


class HotelStore:
    def __init__(self, engine: sa.Engine):
        self.engine = engine

    def create_hotel(self, hotel_id, name: str, city: str) -> tuple[dict, bool]:
        try:
            with self.engine.begin() as conn:
                row = conn.execute(
                    insert(hotels)
                    .values(id=hotel_id, name=name, city=city)
                    .on_conflict_do_nothing(index_elements=[hotels.c.id])
                    .returning(*HOTEL_COLUMNS)
                ).first()
                if row is not None:
                    return dict(row._mapping), True
                existing = conn.execute(
                    sa.select(*HOTEL_COLUMNS).where(hotels.c.id == hotel_id)
                ).one()
        except SQLAlchemyError as exc:
            raise _unavailable(exc) from exc
        hotel = dict(existing._mapping)
        if hotel["name"] != name or hotel["city"] != city:
            raise IdConflict("id de hotel ya usado con otro contenido")
        return hotel, False

    def create_room(
        self, room_id, hotel_id, name: str, capacity: int, price: int, currency: str
    ) -> tuple[dict, bool]:
        try:
            with self.engine.begin() as conn:
                if (
                    conn.execute(
                        sa.select(hotels.c.id).where(hotels.c.id == hotel_id)
                    ).first()
                    is None
                ):
                    raise HotelNotFound("hotel no encontrado")
                row = conn.execute(
                    insert(rooms)
                    .values(
                        id=room_id,
                        hotel_id=hotel_id,
                        name=name,
                        capacity=capacity,
                        price_per_night_cents=price,
                        currency=currency,
                    )
                    .on_conflict_do_nothing(index_elements=[rooms.c.id])
                    .returning(*ROOM_COLUMNS)
                ).first()
                if row is not None:
                    return dict(row._mapping), True
                existing = conn.execute(
                    sa.select(*ROOM_COLUMNS).where(rooms.c.id == room_id)
                ).one()
        except (HotelNotFound, IdConflict):
            raise
        except SQLAlchemyError as exc:
            raise _unavailable(exc) from exc
        room = dict(existing._mapping)
        if (
            room["hotel_id"] != hotel_id
            or room["name"] != name
            or room["capacity"] != capacity
            or room["price_per_night_cents"] != price
            or room["currency"] != currency
        ):
            raise IdConflict("id de habitación ya usado con otro contenido")
        return room, False

    def list_hotels(self, city: str | None = None) -> list[dict]:
        query = sa.select(*HOTEL_COLUMNS).order_by(hotels.c.name, hotels.c.id)
        if city is not None:
            query = query.where(hotels.c.city == city)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query).all()
            return [dict(row._mapping) for row in rows]
        except SQLAlchemyError as exc:
            raise _unavailable(exc) from exc

    def get_hotel(self, hotel_id) -> dict | None:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(*HOTEL_COLUMNS).where(hotels.c.id == hotel_id)
                ).first()
                if row is None:
                    return None
                room_rows = conn.execute(
                    sa.select(*ROOM_COLUMNS)
                    .where(rooms.c.hotel_id == hotel_id)
                    .order_by(rooms.c.name)
                ).all()
        except SQLAlchemyError as exc:
            raise _unavailable(exc) from exc
        hotel = dict(row._mapping)
        hotel["rooms"] = [dict(room._mapping) for room in room_rows]
        return hotel

    def get_room(self, room_id) -> dict | None:
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    sa.select(*ROOM_COLUMNS).where(rooms.c.id == room_id)
                ).first()
            return dict(row._mapping) if row else None
        except SQLAlchemyError as exc:
            raise _unavailable(exc) from exc

    def ping(self) -> None:
        try:
            with self.engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise _unavailable(exc) from exc
