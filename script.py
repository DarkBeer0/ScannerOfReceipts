import os
import base64
import json
import re
import time
import logging
import pandas as pd
from mistralai import Mistral
from config import ApiKey
from tqdm import tqdm
from pdf2image import convert_from_path

# ==========================
# 🔧 Pomocnicze funkcje
# ==========================

def clean_json_text(text: str) -> str:
    """Usuwa znaczniki markdown ```json ... ``` i zbędne spacje."""
    cleaned = re.sub(r"```json\s*|\s*```", "", text.strip(), flags=re.DOTALL)
    return cleaned.strip()


def encode_image(image_path: str) -> str:
    """Koduje obraz do base64, jeśli plik istnieje."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"❌ Plik nie istnieje: {image_path}")
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def is_valid_json(text: str) -> bool:
    """Sprawdza, czy tekst jest poprawnym JSON-em."""
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def convert_pdf_to_jpg(pdf_path: str) -> str:
    """Konwertuje pierwszą stronę PDF na tymczasowy plik JPG."""
    images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)
    temp_path = pdf_path.replace(".pdf", "_page1.jpg")
    images[0].save(temp_path, "JPEG")
    return temp_path


# ==========================
# 💾 Cache system
# ==========================

CACHE_FILE = "cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)


# ==========================
# 🤖 Mistral client
# ==========================

mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY", ApiKey))


# ==========================
# 📄 Ekstrakcja danych z faktury
# ==========================

def extract_invoice_data(image_path: str, retries=3, delay=5):
    """Wydobywa dane z faktury używając Mistral Vision z retry."""
    for attempt in range(1, retries + 1):
        try:
            base64_image = encode_image(image_path)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                """Przeanalizuj tę fakturę i wydobądź następujące dane w formacie JSON:
{
    "numer_faktury": "",
    "data_wystawienia": "",
    "sprzedawca": "",
    "nabywca": "",
    "pozycje": [
        {"nazwa": "", "ilosc": 0, "cena_jedn": 0, "wartosc": 0}
    ],
    "suma_netto": 0,
    "vat": 0,
    "suma_brutto": 0
}
Zwróć tylko JSON, bez dodatkowych komentarzy."""
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": f"data:image/jpeg;base64,{base64_image}",
                        },
                    ],
                }
            ]

            response = mistral.chat.complete(
                model="pixtral-12b-2409",
                messages=messages,
                stream=False,
            )

            if not response.choices:
                raise ValueError("Brak odpowiedzi z API")

            content = response.choices[0].message.content.strip()
            cleaned_content = clean_json_text(content)

            if is_valid_json(cleaned_content):
                return json.loads(cleaned_content)
            else:
                raise ValueError("Niepoprawny JSON")

        except Exception as e:
            print(f"⚠️ Próba {attempt}/{retries} nie powiodła się: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                print("❌ Wszystkie próby nieudane.")
                return None


# ==========================
# 📦 Przetwarzanie folderu
# ==========================

def process_invoices_in_folder(folder_path: str):
    """Przetwarza pliki JPG, PNG, PDF, pokazuje postęp, zapisuje logi i korzysta z cache."""
    logging.basicConfig(
        filename="processing.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8"
    )

    if not os.path.exists(folder_path):
        logging.error(f"Folder nie znaleziony: {folder_path}")
        raise FileNotFoundError(f"❌ Folder nie znaleziony: {folder_path}")

    valid_extensions = (".jpg", ".jpeg", ".png", ".pdf")
    all_invoices = []
    output_buffer = []

    cache = load_cache()
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)]

    for filename in tqdm(files, desc="Przetwarzanie plików"):
        if filename in cache:
            print(f"🧠 {filename} już w cache — pomijam API.")
            all_invoices.append(cache[filename])
            continue

        file_path = os.path.join(folder_path, filename)
        logging.info(f"Przetwarzanie pliku: {filename}")

        try:
            if filename.lower().endswith(".pdf"):
                file_path = convert_pdf_to_jpg(file_path)
                logging.info(f"PDF {filename} przekonwertowany na {file_path}")

            result = extract_invoice_data(file_path)

            if isinstance(result, dict):
                result["plik"] = filename
                all_invoices.append(result)
                cache[filename] = result
                save_cache(cache)
                logging.info(f"✅ Udało się odczytać JSON z {filename}")
                output_buffer.append(f"📄 {filename}:\n{json.dumps(result, indent=4, ensure_ascii=False)}\n")
            else:
                logging.warning(f"⚠️ Nie udało się odczytać JSON z {filename}")
                output_buffer.append(f"⚠️ Nie udało się odczytać JSON z {filename}\n")

        except Exception as e:
            logging.error(f"❌ Błąd przy przetwarzaniu {filename}: {e}")
            output_buffer.append(f"❌ Błąd przy przetwarzaniu {filename}: {e}\n")

    combined = {"faktury": all_invoices}

    print("\n📦 Wszystkie wyniki:\n")
    print("\n".join(output_buffer))
    print("\n✅ Wszystkie faktury połączone w jeden JSON:\n")
    print(json.dumps(combined, indent=4, ensure_ascii=False))

    # 💰 Estymacja kosztu API
    API_COST_PER_CALL = 0.01  # euro per call (dla przykładu)
    total_calls = len(files)
    estimated_cost = total_calls * API_COST_PER_CALL
    print(f"\n💰 Szacowany koszt API: {estimated_cost:.2f} € ({total_calls} zapytań)\n")

    logging.info(f"✅ Przetwarzanie zakończone. Łącznie plików: {len(files)}")

    return combined


# ==========================
# 📊 Tworzenie DataFrame i zapis
# ==========================

def create_dataframe_from_invoices(combined_data: dict) -> pd.DataFrame:
    """Tworzy DataFrame z JSON-a wszystkich faktur i waliduje sumy."""
    if "faktury" not in combined_data or not combined_data["faktury"]:
        print("⚠️ Brak danych faktur do utworzenia DataFrame.")
        return pd.DataFrame()

    invoices = []

    for f in combined_data["faktury"]:
        invoice = {
            "numer_faktury": f.get("numer_faktury"),
            "data_wystawienia": f.get("data_wystawienia"),
            "sprzedawca": f.get("sprzedawca"),
            "nabywca": f.get("nabywca"),
            "suma_netto": f.get("suma_netto"),
            "vat": f.get("vat"),
            "suma_brutto": f.get("suma_brutto"),
            "plik": f.get("plik"),
        }

        expected_brutto = round(float(f.get("suma_netto", 0)) + float(f.get("vat", 0)), 2)
        actual_brutto = round(float(f.get("suma_brutto", 0)), 2)
        invoice["błędna_suma"] = expected_brutto != actual_brutto

        invoices.append(invoice)

    df = pd.DataFrame(invoices)
    print("📊 DataFrame utworzony:")
    print(df)

    df.to_csv("invoices_summary.csv", index=False, encoding="utf-8-sig")
    print("💾 Zapisano CSV: invoices_summary.csv")

    with pd.ExcelWriter("invoices_summary.xlsx", engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Faktury")
    print("💾 Zapisano Excel: invoices_summary.xlsx")

    return df


# ==========================
# 🚀 Uruchomienie programu
# ==========================

if __name__ == "__main__":
    result = process_invoices_in_folder("image")
    df = create_dataframe_from_invoices(result)
