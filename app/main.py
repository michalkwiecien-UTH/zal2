import asyncio
import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

OWM_API_KEY = os.getenv("OWM_API_KEY", "")
WEATHERAPI_KEY = os.getenv("WEATHERAPI_KEY", "")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "5.0"))

app = FastAPI(
    title="Weather Aggregator API",
    description="Agreguje dane pogodowe z 3 zrodel: Open-Meteo, OpenWeatherMap, WeatherAPI",
    version="1.0.0",
)

class SourceData(BaseModel):
    source: str
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    description: Optional[str] = None
    error: Optional[str] = None

class AggregatedWeather(BaseModel):
    city: str
    sources_count: int
    sources_succeeded: int
    average_temperature_c: Optional[float]
    average_humidity_pct: Optional[float]
    sources: list[SourceData]

async def geocode(client: httpx.AsyncClient, city: str) -> tuple[float, float]:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    resp = await client.get(url, params={"name": city, "count": 1})
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        raise HTTPException(status_code=404, detail=f"Nie znaleziono miasta: {city}")
    r = data["results"][0]
    return r["latitude"], r["longitude"]

async def fetch_open_meteo(client: httpx.AsyncClient, lat: float, lon: float) -> SourceData:
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        resp = await client.get(url, params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
        })
        resp.raise_for_status()
        data = resp.json()["current"]
        return SourceData(
            source="Open-Meteo",
            temperature_c=data.get("temperature_2m"),
            humidity_pct=data.get("relative_humidity_2m"),
            description=f"weather_code={data.get('weather_code')}",
        )
    except Exception as e:
        return SourceData(source="Open-Meteo", error=str(e))


async def fetch_owm(client: httpx.AsyncClient, lat: float, lon: float) -> SourceData:
    if not OWM_API_KEY:
        return SourceData(source="OpenWeatherMap", error="Brak klucza OWM_API_KEY w .env")
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        resp = await client.get(url, params={
            "lat": lat,
            "lon": lon,
            "appid": OWM_API_KEY,
            "units": "metric",
        })
        resp.raise_for_status()
        data = resp.json()
        return SourceData(
            source="OpenWeatherMap",
            temperature_c=data["main"]["temp"],
            humidity_pct=data["main"]["humidity"],
            description=data["weather"][0]["description"],
        )
    except Exception as e:
        return SourceData(source="OpenWeatherMap", error=str(e))


async def fetch_weatherapi(client: httpx.AsyncClient, lat: float, lon: float) -> SourceData:
    if not WEATHERAPI_KEY:
        return SourceData(source="WeatherAPI", error="Brak klucza WEATHERAPI_KEY w .env")
    try:
        url = "https://api.weatherapi.com/v1/current.json"
        resp = await client.get(url, params={
            "key": WEATHERAPI_KEY,
            "q": f"{lat},{lon}",
        })
        resp.raise_for_status()
        data = resp.json()
        return SourceData(
            source="WeatherAPI",
            temperature_c=data["current"]["temp_c"],
            humidity_pct=data["current"]["humidity"],
            description=data["current"]["condition"]["text"],
        )
    except Exception as e:
        return SourceData(source="WeatherAPI", error=str(e))

@app.get("/", tags=["meta"])
async def root():
    """Powitalny endpoint - link do dokumentacji."""
    return {
        "service": "Weather Aggregator",
        "docs": "/docs",
        "example": "/weather?city=Warsaw",
    }


@app.get("/health", tags=["meta"])
async def health():
    """Healthcheck dla Dockera."""
    return {"status": "ok"}


@app.get("/weather", response_model=AggregatedWeather, tags=["weather"])
async def get_weather(city: str = Query(..., description="Nazwa miasta, np. Warsaw")):
    """
    Zwraca usrednione dane pogodowe z 3 zrodel:
    Open-Meteo, OpenWeatherMap, WeatherAPI.
    """
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        lat, lon = await geocode(client, city)

        results = await asyncio.gather(
            fetch_open_meteo(client, lat, lon),
            fetch_owm(client, lat, lon),
            fetch_weatherapi(client, lat, lon),
        )
        
    valid_temps = [r.temperature_c for r in results if r.temperature_c is not None]
    valid_hums = [r.humidity_pct for r in results if r.humidity_pct is not None]

    avg_temp = round(sum(valid_temps) / len(valid_temps), 2) if valid_temps else None
    avg_hum = round(sum(valid_hums) / len(valid_hums), 2) if valid_hums else None

    return AggregatedWeather(
        city=city,
        sources_count=len(results),
        sources_succeeded=len(valid_temps),
        average_temperature_c=avg_temp,
        average_humidity_pct=avg_hum,
        sources=results,
    )
