import dataclasses
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import json
import os
import requests
import openai
from bs4 import BeautifulSoup
from dateparser import parse
from dotenv import load_dotenv
import hashlib
import PyPDF2

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_KEY")
PDF_HASH_FILE = "processed_pdf_hashes.json"

URL_LIST = [
    'https://yellowroostercoffee.com/coffees/',
    'https://www.croptocup.com/offers/',
    'https://www.roastmasters.com/new.html',
    'https://www.covoyacoffee.com/origins.html?coffee_status=1171&country_code=US&ctrm_warehouse_name=1551',
    'https://www.roastmasters.com/green_coffee.html',
    'https://www.roastmasters.com/islands_exotics.html',
    'https://royalcoffee.com/crown-jewels/',
    'https://royalcoffee.com/50lb-green-coffee-royal-gems/',
    'https://www.cafeimports.com/north-america/offerings?new=yes',
    'https://www.croptocup.com/forward-offers/',
    # 'https://www.genuineorigin.com/greencoffee?show=100&item-warehouse=East-Coast-PA',
    'https://thecaptainscoffee.com/collections/green-coffee?sort_by=created-descending',
]


@dataclasses.dataclass
class WarehouseData:
    location: Optional[str] = None
    quantity_available: Optional[int] = None


@dataclasses.dataclass
class Size:
    units: Optional[str] = None
    value: Optional[float] = None


@dataclasses.dataclass
class Price:
    units: Optional[str] = None
    value: Optional[float] = None


@dataclasses.dataclass
class GreenData:
    name: Optional[str] = None
    url: Optional[str] = None # For PDFs, this can be the file path
    importer: Optional[str] = None # New field
    farm: Optional[str] = None
    country: Optional[str] = None
    arrival: Optional[date] = None
    cupping_notes: Optional[str] = None
    variety: Optional[str] = None
    quantity_available: List[WarehouseData] = dataclasses.field(default_factory=list)
    size: Optional[Size] = None
    price: Optional[Price] = None
    added: Optional[date] = None
    removed: Optional[date] = None


def calculate_file_hash(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath} for hashing.")
        return ""
    except Exception as e:
        print(f"Error hashing file {filepath}: {e}")
        return ""


def load_processed_pdf_hashes() -> set:
    if not os.path.exists(PDF_HASH_FILE):
        return set()
    try:
        with open(PDF_HASH_FILE, 'r') as f:
            return set(json.load(f))
    except json.JSONDecodeError:
        print(f"Warning: Could not decode {PDF_HASH_FILE}. Starting with an empty set of hashes.")
        return set()
    except Exception as e:
        print(f"Error loading PDF hashes: {e}. Starting with an empty set.")
        return set()


def save_processed_pdf_hashes(hashes: set):
    try:
        with open(PDF_HASH_FILE, 'w') as f:
            json.dump(list(hashes), f, indent=4)
    except Exception as e:
        print(f"Error saving PDF hashes: {e}")


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text() or ""
        return text
    except FileNotFoundError:
        print(f"Error: PDF file not found at {pdf_path}")
        return None
    except Exception as e:
        print(f"Error extracting text from PDF {pdf_path}: {e}")
        return None


def extract_structured_data_from_pdf_text_via_ai(pdf_text_content: str, pdf_filename: str) -> List[GreenData]:
    if not OPENAI_KEY:
        print(f"OpenAI API key not available. Skipping AI extraction for {pdf_filename}.")
        return []

    client = openai.OpenAI(api_key=OPENAI_KEY)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_coffee_data",
                "description": "Extracts a list of green coffee bean details from text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "coffees": {
                            "type": "array",
                            "description": "A list of coffee bean data objects found in the text.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Name of the coffee bean."},
                                    "url": {"type": "string",
                                            "description": "Link to the coffee (if available in text, otherwise file path)."},
                                    "importer": {"type": "string",
                                                 "description": "Name of the importer or company offering the coffee, if identifiable from the text."},
                                    # New property
                                    "farm": {"type": "string", "description": "Name of the farm or estate."},
                                    "country": {"type": "string", "description": "Country of origin."},
                                    "arrival": {"type": "string",
                                                "description": "Arrival date or period (e.g., 'YYYY-MM-DD', 'June 2024', 'Fresh Crop')."},
                                    "cupping_notes": {"type": "string", "description": "Tasting or cupping notes."},
                                    "variety": {"type": "string", "description": "Coffee bean variety."},
                                    "quantity_available": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "location": {"type": "string"},
                                                "quantity_available": {"type": "integer"}
                                            },
                                            "required": []
                                        }
                                    },
                                    "size": {
                                        "type": "object",
                                        "properties": {
                                            "units": {"type": "string"},
                                            "value": {"type": "integer"}
                                        }
                                    },
                                    "price": {
                                        "type": "object",
                                        "properties": {
                                            "units": {"type": "string"},
                                            "value": {"type": "number"}
                                        }
                                    }
                                },
                                "required": ["name"]
                            }
                        }
                    },
                    "required": ["coffees"]
                }
            }
        }
    ]

    try:
        print(f"AI processing for PDF: {pdf_filename}...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "You are an expert data extraction assistant. Extract information about green coffee beans from the provided text extracted from a PDF document using the available tool. For each coffee, try to identify the importer or company offering it if mentioned. If you are asked for a date, and if the string is a 'month year' or just a year, try your best to give a date, don't provide a string. If no coffee data is found, return an empty list of coffees. Only extract information explicitly present in the text."},
                # Modified prompt
                {"role": "user",
                 "content": f"Extract green coffee bean data from the following text content from PDF '{pdf_filename}':\n\n{pdf_text_content[:100000]}"}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "extract_coffee_data"}},
            temperature=0.2,
        )

        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            print(f"AI did not return any tool calls for {pdf_filename}.")
            return []

        function_args_json = tool_calls[0].function.arguments
        ai_output = json.loads(function_args_json)

        extracted_data_list: List[GreenData] = []
        raw_coffees_data = ai_output.get('coffees', [])

        for coffee_dict in raw_coffees_data:
            if not isinstance(coffee_dict, dict):
                print(f"Warning: Expected dict for coffee item, got {type(coffee_dict)}. Skipping.")
                continue

            warehouse_data_list = []
            raw_wh_data = coffee_dict.get('quantity_available', [])
            if isinstance(raw_wh_data, list):
                for wh_item in raw_wh_data:
                    if isinstance(wh_item, dict):
                        warehouse_data_list.append(WarehouseData(**wh_item))

            size_data = coffee_dict.get('size')
            size_obj = Size(**size_data) if isinstance(size_data, dict) else None

            price_data = coffee_dict.get('price')
            price_obj = Price(**price_data) if isinstance(price_data, dict) else None

            arrival_date_str = coffee_dict.get('arrival')
            arrival_date_obj = parse_date_flexible(arrival_date_str)

            item_url = coffee_dict.get('url') or pdf_filename

            green_data_item = GreenData(
                name=coffee_dict.get('name'),
                url=item_url,
                importer=coffee_dict.get('importer'),  # New field assignment
                farm=coffee_dict.get('farm'),
                country=coffee_dict.get('country'),
                arrival=arrival_date_obj,
                cupping_notes=coffee_dict.get('cupping_notes'),
                variety=coffee_dict.get('variety'),
                quantity_available=warehouse_data_list,
                size=size_obj,
                price=price_obj
            )
            extracted_data_list.append(green_data_item)

        print(f"AI extracted {len(extracted_data_list)} items from {pdf_filename}.")
        return extracted_data_list

    except openai.APIError as e:
        print(f"OpenAI API error for {pdf_filename}: {e}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response from AI for {pdf_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during AI extraction for {pdf_filename}: {e}")
    return []
def fetch_html_content(url: str) -> Optional[str]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        body_tag = soup.find('body')

        if body_tag:
            return str(body_tag)
        else:
            print(f"Warning: No <body> tag found in content from {url}. Returning full HTML.")
            return html_content  # Fallback to full HTML if no body tag

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error fetching {url}: {e}")
        if e.response.status_code == 403:
            print(f"  (Forbidden - User-Agent and other headers might not be sufficient for {url})")
        return None
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None
    except Exception as e:  # Catch potential BeautifulSoup errors
        print(f"Error parsing HTML from {url}: {e}")
        return None


def parse_date_flexible(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        dt_obj = parse(date_str)
        return dt_obj.date()
    except Exception as e:
        print(f"Warning: Could not parse date string: {date_str} Exception: {e}")
        return None


def extract_structured_data_via_ai(html_content: str, source_url: str) -> List[GreenData]:
    if not OPENAI_KEY:
        print(f"OpenAI API key not available. Skipping AI extraction for {source_url}.")
        return []

    client = openai.OpenAI(api_key=OPENAI_KEY)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "extract_coffee_data",
                "description": "Extracts a list of green coffee bean details from HTML.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "coffees": {
                            "type": "array",
                            "description": "A list of coffee bean data objects found on the page.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Name of the coffee bean."},
                                    "url": {"type": "string", "description": "Link to the coffee. "},
                                    "farm": {"type": "string", "description": "Name of the farm or estate."},
                                    "country": {"type": "string", "description": "Country of origin."},
                                    "arrival": {"type": "string",
                                                "description": "Arrival date or period (e.g., 'YYYY-MM-DD', 'June 2024', 'Fresh Crop')."},
                                    "cupping_notes": {"type": "string", "description": "Tasting or cupping notes."},
                                    "variety": {"type": "string", "description": "Coffee bean variety."},
                                    "quantity_available": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "location": {"type": "string"},
                                                "quantity_available": {"type": "integer"}
                                            },
                                            "required": []
                                        }
                                    },
                                    "size": {
                                        "type": "object",
                                        "properties": {
                                            "units": {"type": "string"},
                                            "value": {"type": "integer"}
                                        }
                                    },
                                    "price": {
                                        "type": "object",
                                        "properties": {
                                            "units": {"type": "string"},
                                            "value": {"type": "number"}
                                        }
                                    }
                                },
                                "required": ["name"]
                            }
                        }
                    },
                    "required": ["coffees"]
                }
            }
        }
    ]

    try:
        print(f"AI processing for {source_url}...")
        response = client.chat.completions.create(
            model="gpt-4o",  # Or another capable model like "gpt-4-turbo"
            messages=[
                {"role": "system",
                 "content": "You are an expert data extraction assistant. Extract information about green coffee beans from the provided HTML using the available tool. If you are asked for a date, and if the string is a 'month year' or just a year, try your best to give a date, don't provide a string. If no coffee data is found, return an empty list of coffees. Only extract information explicitly present in the HTML."},
                {"role": "user",
                 "content": f"Extract green coffee bean data from the following HTML content from {source_url}:\n\n{html_content[:100000]}"}
            ],
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "extract_coffee_data"}},
            temperature=0.2,
        )

        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            print(f"AI did not return any tool calls for {source_url}.")
            return []

        function_args_json = tool_calls[0].function.arguments
        ai_output = json.loads(function_args_json)

        extracted_data_list: List[GreenData] = []
        raw_coffees_data = ai_output.get('coffees', [])

        for coffee_dict in raw_coffees_data:
            if not isinstance(coffee_dict, dict):
                print(f"Warning: Expected dict for coffee item, got {type(coffee_dict)}. Skipping.")
                continue

            warehouse_data_list = []
            raw_wh_data = coffee_dict.get('quantity_available', [])
            if isinstance(raw_wh_data, list):
                for wh_item in raw_wh_data:
                    if isinstance(wh_item, dict):
                        warehouse_data_list.append(WarehouseData(**wh_item))

            size_data = coffee_dict.get('size')
            size_obj = Size(**size_data) if isinstance(size_data, dict) else None

            price_data = coffee_dict.get('price')
            price_obj = Price(**price_data) if isinstance(price_data, dict) else None

            arrival_date_str = coffee_dict.get('arrival')
            arrival_date_obj = parse_date_flexible(arrival_date_str)

            green_data_item = GreenData(
                name=coffee_dict.get('name'),
                farm=coffee_dict.get('farm'),
                country=coffee_dict.get('country'),
                arrival=arrival_date_obj,
                cupping_notes=coffee_dict.get('cupping_notes'),
                variety=coffee_dict.get('variety'),
                quantity_available=warehouse_data_list,
                size=size_obj,
                price=price_obj
            )
            extracted_data_list.append(green_data_item)

        print(f"AI extracted {len(extracted_data_list)} items for {source_url}.")
        return extracted_data_list

    except openai.APIError as e:
        print(f"OpenAI API error for {source_url}: {e}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response from AI for {source_url}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during AI extraction for {source_url}: {e}")

    return []


class DataClassJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


def main():
    output_data_folder = "green_data"
    os.makedirs(output_data_folder, exist_ok=True)

    source_data_map: Dict[str, List[GreenData]] = {}  # Renamed for clarity
    current_date = date.today()

    while True:
        scrape_choice = input("Would you like to scrape sites or pdfs? (Enter 'sites' or 'pdfs'): ").strip().lower()
        if scrape_choice in ['sites', 'pdfs']:
            break
        print("Invalid choice. Please enter 'sites' or 'pdfs'.")

    if scrape_choice == 'sites':
        for item_url in URL_LIST:
            print(f"Processing URL: {item_url}")
            html = fetch_html_content(item_url)
            if html:
                try:
                    data_items = extract_structured_data_via_ai(html, item_url)
                    for item in data_items:
                        if item.added is None:
                            item.added = current_date
                        if item.url is None:  # Ensure URL from scraping is set
                            item.url = item_url
                    source_data_map[item_url] = data_items
                except Exception as e:
                    print(f"Error during AI processing for {item_url}: {e}")
                    source_data_map[item_url] = []
            else:
                source_data_map[item_url] = []

    elif scrape_choice == 'pdfs':
        pdf_folder_path = "offer_pdfs"
        if not os.path.isdir(pdf_folder_path):
            print(f"Error: Folder not found at {pdf_folder_path}")
            return

        processed_hashes = load_processed_pdf_hashes()
        new_hashes_this_session = set()

        for filename in os.listdir(pdf_folder_path):
            if filename.lower().endswith(".pdf"):
                pdf_path = os.path.join(pdf_folder_path, filename)
                print(f"Processing PDF: {pdf_path}")

                file_hash = calculate_file_hash(pdf_path)
                if not file_hash:
                    continue

                if file_hash in processed_hashes:
                    print(f"Skipping {filename} as it has already been processed (hash: {file_hash[:8]}...).")
                    continue

                pdf_text = extract_text_from_pdf(pdf_path)
                if pdf_text:
                    try:
                        data_items = extract_structured_data_from_pdf_text_via_ai(pdf_text, filename)
                        for item in data_items:
                            if item.added is None:
                                item.added = current_date
                            if item.url is None:
                                item.url = pdf_path
                        source_data_map[pdf_path] = data_items
                        if data_items:
                            new_hashes_this_session.add(file_hash)
                    except Exception as e:
                        print(f"Error during AI processing for PDF {filename}: {e}")
                        source_data_map[pdf_path] = []
                else:
                    source_data_map[pdf_path] = []

        if new_hashes_this_session:
            updated_hashes = processed_hashes.union(new_hashes_this_session)
            save_processed_pdf_hashes(updated_hashes)
            print(f"Updated processed PDF hashes in {PDF_HASH_FILE}")

    filename_date_stamp = datetime.now().strftime("%Y%m%d")
    scrape_type_suffix = "sites" if scrape_choice == "sites" else "pdfs"
    json_output_path = os.path.join(output_data_folder,
                                    f"daily_coffee_data_{scrape_type_suffix}_{filename_date_stamp}.json")

    with open(json_output_path, 'w') as json_file:
        json.dump(source_data_map, json_file, cls=DataClassJSONEncoder, indent=4)

    print(f"Structured data saved to {json_output_path}")


if __name__ == "__main__":
    main()
