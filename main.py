"""
Лабораторная работа №1: HTTP-клиент к SampleAPIs Coffee.

Описание запроса создания горячего кофе (POST /coffee/hot/)
============================================================

HTTP-метод и URL:
    POST https://pycourse-2026.duckdns.org/coffee/hot/

Заголовки:
    Content-Type: application/json  — тело в формате JSON.
    Accept: application/json        — ожидаем JSON-ответ.

JSON-тело запроса (поля объекта напитка):
    title        : string,    обязательное, непустое. Название напитка.
    description  : string,    обязательное, непустое. Описание.
    ingredients  : list[str], обязательное, минимум один элемент.
    image        : string,    необязательное. URL картинки.

Ограничения на значения:
    - title и description — непустые строки;
    - ingredients — непустой массив непустых строк.

Поля, которые создаёт сервер:
    id : int — присваивается сервером, клиент его не отправляет.

Ожидаемый успешный статус:
    201 Created (в некоторых версиях — 200 OK).
    В ответе — JSON-объект созданного напитка с полем id.

Подтверждено реальными запросами:
    - id генерируется сервером и приходит в ответе на POST;
    - GET по несуществующему id возвращает 404;
    - DELETE возвращает 200 с телом или 204 без тела.

Локальная валидация только в клиенте:
    - непустые title, description;
    - непустой список ingredients.
"""

import requests
from uuid import uuid4

JsonObject = dict[str, object]

API_BASE_URL = "https://pycourse-2026.duckdns.org/coffee/hot/"
DEFAULT_TIMEOUT = 10.0


class CoffeeApiError(Exception):
    """Общая ошибка при работе с Coffee API."""


class CoffeeNotFoundError(CoffeeApiError):
    """Запрошенный напиток не найден (HTTP 404)."""


class SampleApisCoffeeClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # ---------- публичные методы ----------

    def list_drinks(self) -> list[JsonObject]:
        response = self._request("GET")
        data = self._parse_json(response)
        if not isinstance(data, list):
            raise CoffeeApiError(
                f"Ожидался список напитков, получено: {type(data).__name__}"
            )
        return data

    def get_drink(self, drink_id: int) -> JsonObject:
        response = self._request("GET", f"/{drink_id}")
        data = self._parse_json(response)
        if not isinstance(data, dict):
            raise CoffeeApiError(
                f"Ожидался объект напитка, получено: {type(data).__name__}"
            )
        return data

    def create_drink(self, payload: JsonObject) -> JsonObject:
        self._validate_payload(payload)
        response = self._request("POST", payload=payload)
        data = self._parse_json(response)
        if not isinstance(data, dict):
            raise CoffeeApiError(
                f"Ожидался объект созданного напитка, получено: {type(data).__name__}"
            )
        if "id" not in data:
            raise CoffeeApiError(
                "Сервер не вернул id созданного напитка — "
                "продолжать сценарий небезопасно."
            )
        return data

    def replace_drink(self, drink_id: int, payload: JsonObject) -> JsonObject:
        self._validate_payload(payload)
        response = self._request("PUT", f"/{drink_id}", payload=payload)
        data = self._parse_json(response)
        if not isinstance(data, dict):
            raise CoffeeApiError(
                f"Ожидался объект напитка после PUT, получено: {type(data).__name__}"
            )
        return data

    def update_drink(self, drink_id: int, changes: JsonObject) -> JsonObject:
        if not changes:
            raise ValueError("PATCH без изменений не имеет смысла.")
        response = self._request("PATCH", f"/{drink_id}", payload=changes)
        data = self._parse_json(response)
        if not isinstance(data, dict):
            raise CoffeeApiError(
                f"Ожидался объект напитка после PATCH, получено: {type(data).__name__}"
            )
        return data

    def delete_drink(self, drink_id: int) -> None:
        response = self._request("DELETE", f"/{drink_id}")
        if response.status_code == 204 or not response.content:
            return
        if response.headers.get("Content-Type", "").startswith("application/json"):
            try:
                response.json()
            except ValueError:
                pass

    # ---------- внутренняя HTTP-логика ----------

    def _request(
        self,
        method: str,
        path: str = "",
        payload: JsonObject | None = None,
    ) -> requests.Response:
        url = f"{self._base_url}{path}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "CourseClient/1.0 (lab-1)",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"

        try:
            response = requests.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
        except requests.exceptions.Timeout as error:
            raise CoffeeApiError(
                f"Тайм-аут при {method} {url} (timeout={self._timeout}s)."
            ) from error
        except requests.exceptions.ConnectionError as error:
            raise CoffeeApiError(
                f"Сетевая ошибка при {method} {url}: {error}"
            ) from error
        except requests.exceptions.RequestException as error:
            raise CoffeeApiError(
                f"Ошибка запроса {method} {url}: {error}"
            ) from error

        if response.status_code == 404:
            raise CoffeeNotFoundError(f"{method} {url} — ресурс не найден (404).")

        if not response.ok:
            snippet = response.text[:200].replace("\n", " ")
            raise CoffeeApiError(
                f"{method} {url} вернул {response.status_code}: {snippet}"
            )

        return response

    @staticmethod
    def _parse_json(response: requests.Response) -> object:
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type.lower():
            raise CoffeeApiError(
                f"Ожидался JSON, получен Content-Type={content_type!r}."
            )
        if not response.content:
            raise CoffeeApiError("Сервер вернул пустое тело вместо JSON.")
        try:
            return response.json()
        except ValueError as error:
            raise CoffeeApiError(f"Не удалось разобрать JSON: {error}") from error

    @staticmethod
    def _validate_payload(payload: JsonObject) -> None:
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Поле 'title' должно быть непустой строкой.")

        description = payload.get("description")
        if description is not None:
            if not isinstance(description, str) or not description.strip():
                raise ValueError("Поле 'description' должно быть непустой строкой.")

        ingredients = payload.get("ingredients")
        if ingredients is not None:
            if not isinstance(ingredients, list) or not ingredients:
                raise ValueError("Поле 'ingredients' должно быть непустым списком.")
            for item in ingredients:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(
                        "Все элементы 'ingredients' должны быть непустыми строками."
                    )


# ---------- сценарий ----------

def _assert_equal(actual: object, expected: object, what: str) -> None:
    if actual != expected:
        raise CoffeeApiError(
            f"Проверка {what} не прошла: ожидали {expected!r}, получили {actual!r}."
        )


def main() -> int:
    client = SampleApisCoffeeClient()
    marker = uuid4().hex[:8]
    created_id: int | None = None

    try:
        print(f"== Метка группы: {marker} ==")

        print("\n[1/8] GET коллекции /coffee/hot/")
        drinks = client.list_drinks()
        print(f"    Получено напитков: {len(drinks)}")
        if drinks:
            first = drinks[0]
            print(f"    Пример: id={first.get('id')}, title={first.get('title')!r}")

        print("\n[2/8] POST — создаём новый напиток с меткой группы")
        create_payload: JsonObject = {
            "title": f"Lab-1 Espresso [{marker}]",
            "description": "Горячий эспрессо, созданный в рамках лабораторной работы.",
            "ingredients": ["Espresso", "Water"],
            "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/A_small_cup_of_coffee.JPG/640px-A_small_cup_of_coffee.JPG",
        }
        created = client.create_drink(create_payload)
        created_id = int(created["id"])
        print(f"    Создан напиток id={created_id}")
        print(f"    title={created.get('title')!r}")

        print(f"\n[3/8] GET /coffee/hot/{created_id}")
        fetched = client.get_drink(created_id)
        _assert_equal(fetched.get("title"), create_payload["title"], "title после POST")
        _assert_equal(
            fetched.get("description"),
            create_payload["description"],
            "description после POST",
        )
        _assert_equal(
            list(fetched.get("ingredients") or []),
            list(create_payload["ingredients"]),
            "ingredients после POST",
        )
        print("    Поля совпадают с отправленными.")

        print(f"\n[4/8] PUT /coffee/hot/{created_id} — полная замена")
        replace_payload: JsonObject = {
            "title": f"Lab-1 Espresso (updated) [{marker}]",
            "description": "Обновлённое описание после PUT.",
            "ingredients": ["Espresso", "Water", "Sugar"],
            "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/A_small_cup_of_coffee.JPG/640px-A_small_cup_of_coffee.JPG",
        }
        replaced = client.replace_drink(created_id, replace_payload)
        _assert_equal(replaced.get("title"), replace_payload["title"], "title после PUT")
        _assert_equal(
            list(replaced.get("ingredients") or []),
            list(replace_payload["ingredients"]),
            "ingredients после PUT",
        )
        print("    PUT применился, поля обновлены.")

        print(f"\n[5/8] PATCH /coffee/hot/{created_id} — частичное изменение")
        patch_payload: JsonObject = {"description": "Описание после PATCH."}
        patched = client.update_drink(created_id, patch_payload)
        _assert_equal(
            patched.get("description"),
            patch_payload["description"],
            "description после PATCH",
        )
        _assert_equal(
            patched.get("title"),
            replace_payload["title"],
            "title не должен меняться при PATCH",
        )
        print("    PATCH изменил только описание, title сохранился.")

        print(f"\n[6/8] GET /coffee/hot/{created_id} — подтверждаем изменения")
        final_state = client.get_drink(created_id)
        _assert_equal(
            final_state.get("description"),
            patch_payload["description"],
            "description после повторного GET",
        )
        _assert_equal(
            final_state.get("title"),
            replace_payload["title"],
            "title после повторного GET",
        )
        print("    Состояние на сервере соответствует ожиданиям.")

        print(f"\n[7/8] DELETE /coffee/hot/{created_id}")
        client.delete_drink(created_id)
        print("    DELETE выполнен.")

        print(f"\n[8/8] GET /coffee/hot/{created_id} — ожидаем 404")
        try:
            client.get_drink(created_id)
        except CoffeeNotFoundError:
            print("    Получен ожидаемый 404 — ресурс удалён.")
            created_id = None
        else:
            raise CoffeeApiError("После DELETE ресурс всё ещё доступен — что-то не так.")

        print("\nСценарий завершён успешно.")
        return 0

    except (CoffeeApiError, ValueError) as error:
        print(f"\nОшибка: {error}. Метка группы: {marker}")
        return 1

    finally:
        if created_id is not None:
            print(f"\nОчистка: удаляем id={created_id}")
            try:
                client.delete_drink(created_id)
                print(f"    Удалено id={created_id}")
            except CoffeeNotFoundError:
                print(f"    id={created_id} уже отсутствует на сервере.")
            except CoffeeApiError as error:
                print(
                    f"    Не удалось удалить id={created_id}: {error}\n"
                    f"    Проверьте вручную метку группы: {marker}"
                )


if __name__ == "__main__":
    raise SystemExit(main())
