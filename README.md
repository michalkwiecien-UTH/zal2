# Weather Aggregator API

Proste API w Pythonie (FastAPI), które po podaniu nazwy miasta odpytuje równolegle trzy publiczne serwisy pogodowe (Open-Meteo, OpenWeatherMap, WeatherAPI), uśrednia wyniki i zwraca jeden ujednolicony JSON. Całość uruchamiana w kontenerze Docker.

## Jak to działa

Aplikacja przyjmuje zapytanie HTTP, zamienia nazwę miasta na współrzędne geograficzne (geokodowanie przez Open-Meteo), a następnie używa `asyncio.gather()` do **równoległego** odpytania wszystkich trzech źródeł. Każde źródło ma własną obsługę błędów — jeśli jedno padnie, średnia liczona jest z pozostałych. Wynik zawiera średnią temperaturę i wilgotność oraz indywidualne dane z każdego API.

Obraz Docker wykorzystuje **multi-stage build** — w pierwszym etapie (`python:3.12-alpine`) pip instaluje zależności do osobnego prefixu, w drugim do finalnego obrazu trafiają tylko zainstalowane paczki i kod aplikacji. Bez cache pip, bez narzędzi buildowych. Kontener działa jako użytkownik non-root.

Konfiguracja (klucze API, port, timeout) jest w pliku `.env` — żadnych haseł zaszytych w kodzie.

## Architektura

Aplikacja składa się z jednego kontenera, w którym działa serwer ASGI **Uvicorn** uruchamiający framework **FastAPI**. FastAPI definiuje endpointy REST, waliduje dane przez **Pydantic** i automatycznie generuje dokumentację OpenAPI (dostępną pod `/docs` jako Swagger UI). Do komunikacji z zewnętrznymi API używana jest asynchroniczna biblioteka **httpx**, co pozwala odpytywać wszystkie źródła równolegle w jednym wątku.

Stack: Python 3.12 (Alpine), FastAPI, Uvicorn, httpx, Pydantic. Konteneryzacja przez Docker z multi-stage buildem i orkiestracja przez Docker Compose. Konfiguracja wczytywana ze zmiennych środowiskowych (`.env`), z domyślnym healthcheckiem sprawdzającym endpoint `/health`.

Komunikacja zewnętrzna: kontener nasłuchuje na porcie 8000 (mapowanym na port hosta z `APP_PORT`), a wychodzące zapytania HTTPS idą do trzech publicznych API pogodowych. 

## Uruchomienie

```bash
cp .env.example .env
# Wklej swoje klucze API do .env
docker compose up -d --build
```

Aplikacja: http://localhost:8000
Dokumentacja (Swagger UI): http://localhost:8000/docs

Zatrzymanie:

```bash
docker compose down
```
