import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from operator import itemgetter
from threading import Thread
from time import sleep
from typing import Iterable, Any

import psycopg2


@dataclass
class GeoLocation:
    lat: float
    lon: float


class UserLocationsStorage(ABC):
    @abstractmethod
    def keys(self, user_id: int) -> Iterable[str]:
        pass

    @abstractmethod
    def delete(self, user_id: int, location_name: str) -> None:
        pass

    @abstractmethod
    def add(self, user_id: int, location_name: str, location: GeoLocation) -> None:
        pass

    @abstractmethod
    def get(self, user_id: int, location_name: str) -> GeoLocation:
        pass


class DictUserLocationsStorage(UserLocationsStorage):
    def get(self, user_id: int, location_name: str) -> GeoLocation:
        return self._storage[user_id][location_name]

    def __init__(self, storage: dict[int, dict[str, GeoLocation]]):
        self._storage = storage

    def keys(self, user_id: int) -> Iterable[str]:
        return list(self._storage.get(user_id, {}).keys())

    def delete(self, user_id: int, location_name: str) -> None:
        try:
            del self._storage[user_id][location_name]
        except KeyError:
            pass

    def add(self, user_id: int, location_name: str, location: GeoLocation) -> None:
        if user_id not in self._storage:
            self._storage[user_id] = dict()

        self._storage[user_id][location_name] = location


@dataclass
class PostgresUserLocationsStorageConfig:
    host: str = os.environ["POSTGRES_HOST"]
    db: str = os.environ["POSTGRES_DB"]
    user: str = os.environ["POSTGRES_USER"]
    password: str = os.environ["POSTGRES_PASSWORD"]

    def connect(self, autocommit: bool = True):
        connection = psycopg2.connect(
            host=self.host,
            database=self.db,
            user=self.user,
            password=self.password,
        )
        connection.autocommit = autocommit

        return connection


class DBConnectionException(Exception):
    pass


def _handle_operational_error(func):
    def wrapped(self: "PostgresUserLocationsStorage", *args: Any, **kwargs: Any) -> Any:
        try:
            return func(self, *args, **kwargs)
        except psycopg2.OperationalError as exc:
            self._connection_error_msg = str(exc)
            self._connection = None

            raise DBConnectionException(self._connection_error_msg)
    return wrapped


class PostgresUserLocationsStorage(UserLocationsStorage):
    def __init__(self, config: PostgresUserLocationsStorageConfig):
        self._config = config

        self._connection = None
        self._connection_error_msg: str | None = ""
        self._stop = False

        self._try_to_connect()

        self._reconnection_thread = Thread(target=self._reconnect_if_needed)
        self._reconnection_thread.start()

    def _try_to_connect(self) -> None:
        if self._connection is None:
            try:
                self._connection = self._config.connect()
            except psycopg2.OperationalError as exc:
                self._connection_error_msg = str(exc)

    def _reconnect_if_needed(self) -> None:
        while not self._stop:
            if self._connection is None:
                self._try_to_connect()
            sleep(3)

    def _new_cursor(self):
        try:
            cursor = self._connection.cursor()
            return cursor
        except AttributeError:
            raise DBConnectionException(self._connection_error_msg)

    @_handle_operational_error
    def keys(self, user_id: int) -> Iterable[str]:
        cursor = self._new_cursor()

        sql = "SELECT location_name FROM locations WHERE user_id=%s;"
        cursor.execute(sql, (user_id,))

        keys = set(map(itemgetter(0), cursor.fetchall()))
        cursor.close()
        return keys

    @_handle_operational_error
    def delete(self, user_id: int, location_name: str) -> None:
        cursor = self._new_cursor()

        sql = "DELETE FROM locations WHERE user_id=%s AND location_name=%s;"
        cursor.execute(sql, (user_id, location_name))
        cursor.close()

    @_handle_operational_error
    def add(self, user_id: int, location_name: str, location: GeoLocation) -> None:
        cursor = self._new_cursor()

        sql = (
            "INSERT INTO locations (user_id, location_name, latitude, longitude) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (user_id, location_name) DO UPDATE SET "
            "   latitude = excluded.latitude, "
            "   longitude = excluded.longitude;"
        )
        cursor.execute(sql, (user_id, location_name, location.lat, location.lon))
        cursor.close()

    @_handle_operational_error
    def get(self, user_id: int, location_name: str) -> GeoLocation:
        cursor = self._new_cursor()

        sql = "SELECT latitude, longitude FROM locations WHERE user_id=%s AND location_name=%s;"
        cursor.execute(sql, (user_id, location_name))

        res = cursor.fetchall()
        if len(res) == 0:
            cursor.close()
            raise KeyError
        cursor.close()

        lat, lon = res[0][0], res[0][1]
        return GeoLocation(lat=lat, lon=lon)

    def stop(self) -> None:
        self._stop = True
        self._reconnection_thread.join()
