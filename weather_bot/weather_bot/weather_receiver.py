import os
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Optional

import requests
import yaml
from requests import Response


@dataclass
class WeatherReceiverConfig:
    api_url: str = os.environ["WEATHER_API_URL"]
    lang: str = os.environ["WEATHER_LANG"]
    token: str = os.environ["WEATHER_TOKEN"]
    translations_config: str = os.environ["WEATHER_TRANSLATIONS_CONFIG"]


class WeatherRequestFailedException(Exception):
    def __init__(self, response: Response) -> None:
        assert response.status_code != 200

        exception_msg = f"{response.status_code}: {response.text}"

        super().__init__(exception_msg)


@dataclass
class DayPartForecast:
    part_name: str
    expected_condition: str

    def __str__(self) -> str:
        return f"{self.part_name}: {self.expected_condition}"


@dataclass
class DayForecast:
    date: str
    parts: list[DayPartForecast]

    def __str__(self) -> str:
        str_ = f"*{self.date}*\n"
        str_ += "\n".join(map(str, self.parts))
        return str_


@dataclass
class Forecasts:
    forecasts: list[DayForecast]

    def __len__(self) -> int:
        len_ = 0
        for forecast in self.forecasts:
            for _ in forecast.parts:
                len_ += 1
        return len_

    def __str__(self) -> str:
        if self.forecasts:
            return "\n\n".join(map(str, self.forecasts))
        else:
            return ""


@dataclass
class YandexWeatherParsedResponse:
    forecasts: Forecasts | None
    until_date: str | None

    def __str__(self) -> str:
        if self.forecasts and len(self.forecasts) > 0:
            return str(self.forecasts)
        elif self.until_date:
            return f"Осадки не ожидаются вплоть до {self.until_date}"
        else:
            return f"В ближайшее время осадки не ожидаются"


class WeatherReceiver:
    def __init__(self, config: WeatherReceiverConfig) -> None:
        self._config = config

        _ = self._translations  # dry load to check whether the config file exists

    @cached_property
    def _translations(self) -> dict[str, Any]:
        with open(self._config.translations_config, "rt") as stream:
            return yaml.safe_load(stream=stream)

    def _get_json_response(self, lat: float, lon: float) -> dict[str, Any]:
        response = requests.get(
            self._config.api_url,
            params={
                "lat": lat,
                "lon": lon,
                "lang": self._config.lang,
            },
            headers={
                "X-Yandex-API-Key": self._config.token,
            }
        )

        if response.status_code != 200:
            raise WeatherRequestFailedException(response=response)

        json_response = response.json()
        return json_response

    def _parse_json_response(self, json_response: dict[str, Any]) -> YandexWeatherParsedResponse:
        forecasts: list[DayForecast] = list()

        last_date: str | None = None

        for forecast_json in json_response.get("forecasts", []):
            try:
                date = forecast_json["date"]
                last_date = date
            except KeyError:
                continue

            parts: list[DayPartForecast] = list()

            for part_name, part_forecast in forecast_json.get("parts", {}).items():
                condition = part_forecast.get("condition")

                part_name_translation = self._translations.get("target_parts", {}).get(part_name)
                condition_translation = self._translations.get("target_conditions", {}).get(condition)

                if part_name_translation and condition_translation:
                    parts.append(DayPartForecast(
                        part_name=part_name_translation,
                        expected_condition=condition_translation
                    ))

            if parts:
                forecasts.append(DayForecast(
                    date=date,
                    parts=parts,
                ))

        parsed_response = YandexWeatherParsedResponse(forecasts=Forecasts(forecasts), until_date=last_date)
        return parsed_response

    def request_weather(self, lat: float, lon: float) -> YandexWeatherParsedResponse:
        json_response = self._get_json_response(lat=lat, lon=lon)
        parsed_response = self._parse_json_response(json_response=json_response)
        return parsed_response
