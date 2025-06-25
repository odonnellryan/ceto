import dataclasses
from datetime import date, datetime
from typing import Optional, List, Dict, Any
import json
import os
import glob
from thefuzz import fuzz  # For fuzzy string matching


# --- Dataclass definitions (copied from your provided code for standalone functionality) ---
@dataclasses.dataclass
class WarehouseData:
    location: Optional[str] = None
    quantity_available: Optional[int] = None


@dataclasses.dataclass
class Size:
    units: Optional[str] = None
    value: Optional[float] = None  # Changed to float to match user's definition


@dataclasses.dataclass
class Price:
    units: Optional[str] = None
    value: Optional[float] = None


@dataclasses.dataclass
class GreenData:
    name: Optional[str] = None
    url: Optional[str] = None
    importer: Optional[str] = None  # Added field
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


SIMILARITY_THRESHOLD_NAME = 85
SIMILARITY_THRESHOLD_COUNTRY = 95
SIMILARITY_THRESHOLD_FARM = 80

def _parse_iso_date(date_str: Optional[str]) -> Optional[date]:
    """Safely parses an ISO format date string to a date object."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        # Fallback for unexpected date formats, though JSON should be ISO.
        print(f"Warning: Could not parse date string '{date_str}' as ISO date.")
        return None


def _dict_to_greendata(data_dict: Dict[str, Any]) -> GreenData:
    """Converts a dictionary (from JSON) to a GreenData object."""
    return GreenData(
        name=data_dict.get('name'),
        url=data_dict.get('url'),
        importer=data_dict.get('importer'),  # Added line
        farm=data_dict.get('farm'),
        country=data_dict.get('country'),
        arrival=_parse_iso_date(data_dict.get('arrival')),
        cupping_notes=data_dict.get('cupping_notes'),
        variety=data_dict.get('variety'),
        quantity_available=[WarehouseData(**wh) for wh in data_dict.get('quantity_available', []) if
                            isinstance(wh, dict)],
        size=Size(**data_dict['size']) if data_dict.get('size') and isinstance(data_dict['size'], dict) else None,
        price=Price(**data_dict['price']) if data_dict.get('price') and isinstance(data_dict['price'], dict) else None,
        added=_parse_iso_date(data_dict.get('added')),
        removed=_parse_iso_date(data_dict.get('removed'))
    )


def load_coffee_data_from_file(file_path: str) -> Dict[str, List[GreenData]]:
    """Loads coffee data from a JSON file and converts it to GreenData objects."""
    try:
        with open(file_path, 'r') as f:
            raw_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found - {file_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from - {file_path}")
        return {}

    structured_data: Dict[str, List[GreenData]] = {}
    for site_url, offerings_list in raw_data.items():
        if not isinstance(offerings_list, list):
            print(f"Warning: Expected a list of offerings for URL '{site_url}', got {type(offerings_list)}. Skipping.")
            structured_data[site_url] = []
            continue

        structured_data[site_url] = [_dict_to_greendata(item) for item in offerings_list if isinstance(item, dict)]
    return structured_data


def find_latest_json_files(directory: str, source_type: str) -> tuple[
    Optional[str], Optional[str]]:
    """
    Finds the latest and second latest JSON files for a specific source type
    in a directory based on date in filename.
    Filename format: daily_coffee_data_{source_type}_YYYYMMDD.json
    """
    file_prefix = f"daily_coffee_data_{source_type}_"
    file_pattern = os.path.join(directory, f"{file_prefix}*.json")
    files = glob.glob(file_pattern)

    dated_files = []
    for f_path in files:
        filename = os.path.basename(f_path)
        try:
            # Remove prefix and suffix to get the date string
            date_str = filename[len(file_prefix):-len(".json")]
            file_date = datetime.strptime(date_str, "%Y%m%d").date()
            dated_files.append((file_date, f_path))
        except ValueError:
            print(f"Warning: Could not parse date from filename: {filename} with prefix {file_prefix}")
            continue

    dated_files.sort(key=lambda x: x[0], reverse=True)

    if len(dated_files) >= 2:
        return dated_files[0][1], dated_files[1][1]  # latest, second_latest
    elif len(dated_files) == 1:
        return dated_files[0][1], None  # only one file
    return None, None


def are_offerings_similar(offering1: GreenData, offering2: GreenData) -> bool:
    if not offering1.name or not offering2.name:
        return True


    name_similarity = fuzz.ratio(offering1.name.lower(), offering2.name.lower())
    if name_similarity < SIMILARITY_THRESHOLD_NAME:
        return False

    if offering1.country and offering2.country:
        country_similarity = fuzz.ratio(offering1.country.lower(), offering2.country.lower())
        if country_similarity < SIMILARITY_THRESHOLD_COUNTRY:
            if name_similarity < (SIMILARITY_THRESHOLD_NAME + 5):
                return False
    elif (offering1.country and offering2.country) and offering1.country != offering2.country:
        return False

    if offering1.farm and offering1.farm.strip() and offering2.farm and offering2.farm.strip():
        farm_similarity = fuzz.ratio(offering1.farm.lower(), offering2.farm.lower())
        if farm_similarity < SIMILARITY_THRESHOLD_FARM:
            return False

    return True


def compare_coffee_data(
        old_data: Dict[str, List[GreenData]],
        new_data: Dict[str, List[GreenData]]
) -> List[Dict[str, Any]]:
    new_offerings_report: List[Dict[str, Any]] = []

    for site_url, new_offerings_list in new_data.items():
        old_offerings_list = old_data.get(site_url, [])
        if not old_offerings_list:
            continue

        for new_item in new_offerings_list:
            if not new_item.name:  # Skip items without a name
                print(f"Warning: New item from {site_url} has no name, skipping: {new_item}")
                continue

            is_truly_new = True
            for old_item in old_offerings_list:
                if not old_item.name:  # Skip old items without a name for comparison
                    continue
                if are_offerings_similar(new_item, old_item):
                    is_truly_new = False
                    break

            if is_truly_new:
                new_offerings_report.append({
                    "source_site": site_url,
                    "offering": dataclasses.asdict(new_item)  # Store as dict for easy serialization/inspection
                })

    return new_offerings_report


def main_comparison():
    data_folder = "green_data"
    source_types = ["sites", "pdfs"]
    all_newly_found_offerings: List[Dict[str, Any]] = []
    processed_any_files = False

    for source_type in source_types:
        print(f"\nProcessing source type: {source_type.upper()}")
        latest_file_path, prior_file_path = find_latest_json_files(data_folder, source_type)

        if not latest_file_path:
            print(f"No data files found for {source_type}.")
            continue

        processed_any_files = True
        print(f"Latest {source_type} file: {os.path.basename(latest_file_path)}")
        latest_data = load_coffee_data_from_file(latest_file_path)
        if not latest_data and os.path.exists(latest_file_path):  # File exists but empty or malformed
            print(f"Warning: Latest {source_type} file {latest_file_path} loaded no data.")

        if not prior_file_path:
            continue
        else:
            print(f"Prior {source_type} file: {os.path.basename(prior_file_path)}")
            prior_data = load_coffee_data_from_file(prior_file_path)
            if not prior_data and os.path.exists(prior_file_path):
                print(f"Warning: Prior {source_type} file {prior_file_path} loaded no data.")

            # If prior_data is empty (e.g. first run after file existed but was empty), treat all as new
            if not prior_data:
                print(f"Prior {source_type} data is empty. Reporting all items from latest {source_type} file as new.")
                for source_key, offerings_list in latest_data.items():
                    for item in offerings_list:
                        if item.name:
                            all_newly_found_offerings.append({
                                "source_file_type": source_type,
                                "source_document": source_key,
                                "offering": dataclasses.asdict(item)
                            })
            else:
                newly_found_for_source = compare_coffee_data(prior_data, latest_data)
                for new_offering_info in newly_found_for_source:
                    # Add source_file_type for clarity in combined report
                    new_offering_info["source_file_type"] = source_type
                    # Rename "source_site" to "source_document" for generality
                    new_offering_info["source_document"] = new_offering_info.pop("source_site")
                    all_newly_found_offerings.append(new_offering_info)

    if not processed_any_files:
        print("No data files found to compare for any source type.")
        return

    if all_newly_found_offerings:
        print(f"\nFound {len(all_newly_found_offerings)} new offerings in total:")
        for new_offering_info in all_newly_found_offerings:
            offering_name = new_offering_info['offering'].get('name', 'N/A')
            offering_country = new_offering_info['offering'].get('country', 'N/A')
            importer_name = new_offering_info['offering'].get('importer', 'N/A')
            print(f"  - Type: {new_offering_info['source_file_type']}, Source: {new_offering_info['source_document']}")
            print(f"    Name: {offering_name}, Country: {offering_country}, Importer: {importer_name}")

        output_filename = f"new_offerings_report_combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_filename, 'w') as f:
            json.dump(all_newly_found_offerings, f, indent=4, default=str)
        print(f"\nCombined new offerings report saved to: {output_filename}")
    else:
        print("\nNo new offerings found across all sources.")


if __name__ == "__main__":
    main_comparison()