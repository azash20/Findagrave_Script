import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
import js2py

# Config
MEMORIAL_URL = "https://www.findagrave.com/memorial/7236403/archibald-mathies"
OUTPUT_FILE = "archibald_mathies_memorial.xlsx"
ERROR_LOG = "errors.txt"

def log_error(msg):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(msg.strip() + "\n")

# Step 1: Fetch page
try:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    }
    response = requests.get(MEMORIAL_URL, headers=headers)
    response.raise_for_status()
except Exception as e:
    log_error(f"[CRITICAL] Failed to fetch page: {e}")
    raise SystemExit("Failed to fetch the page. Check errors.txt.")

# Step 2: Parse HTML
soup = BeautifulSoup(response.text, "html.parser")

# Step 3: Extract JS object
try:
    script_tag = soup.find("script", string=re.compile(r"var\s+findagrave\s*="))
    if not script_tag:
        raise ValueError("Missing 'findagrave' JS object")

    raw_script = script_tag.string
    match = re.search(r"var\s+findagrave\s*=\s*({.*?});\s*var\s+htmlSnippets", raw_script, re.DOTALL)
    if not match:
        raise ValueError("Failed to extract 'findagrave' object")

    js_code = "var findagrave = " + match.group(1) + "; findagrave;"
    data = js2py.eval_js(js_code)
except Exception as e:
    log_error(f"[CRITICAL] JS parsing failed: {e}")
    raise SystemExit("JS parsing failed. Check errors.txt.")

# Step 4: Extract main fields from JS with cleaned full_name
try:
    # Clean full_name if it contains HTML tags like <span class="prefix">
    raw_full_name = data.fullName
    soup_name = BeautifulSoup(raw_full_name, "html.parser")
    for span in soup_name.select("span.prefix"):
        span.decompose()
    cleaned_full_name = soup_name.get_text(strip=True)

    main_fields = {
        "full_name": cleaned_full_name,
        "first_name": data.firstName,
        "last_name": data.lastName,
        "birth_year": data.birthYear,
        "death_year": data.deathYear,
        "death_date": data.deathDate,
        "death_month": data.deathMonth,
        "death_day": data.deathDay,
        "cemetery_name": data.cemeteryName,
        "cemetery_city": data.cemeteryCityName,
        "cemetery_county": data.cemeteryCountyName,
        "cemetery_state": data.cemeteryStateName,
        "cemetery_country": data.cemeteryCountryName,
        "cemetery_latitude": data.cemeteryLatitude,
        "cemetery_longitude": data.cemeteryLongitude,
        "memorial_id": data.memorialId,
        "person_id": data.personId,
        "memorial_contributor_id": data.memorialContributorId,
        "sponsor_contributor_id": data.sponsorContributorId,
        "memorial_url": data.linkToShare,
        "is_famous": data.isFamous,
        "is_cenotaph": data.isCenotaph,
        "has_grave_photo": data.intermentHasPhoto,
        "cover_photo_id": data.coverPhotoId,
        "cover_photo_url": data.photoToShare,
        "default_photo_url": data.defaultPhotoToShare,
        "cemetery_id": data.memorialCemeteryId,
    }
except Exception as e:
    log_error(f"[DATA] Failed to extract main_fields: {e}")

# Step 5: Extract biography (and bio contributor)
try:
    bio_div = soup.find("div", id="partBio")
    main_fields["biography"] = bio_div.get_text(strip=True) if bio_div else ""

    contributor = soup.find("p", class_="text-muted")
    if contributor and contributor.find("a"):
        main_fields["bio_by"] = contributor.find("a").get_text(strip=True)
    else:
        main_fields["bio_by"] = ""
except Exception as e:
    log_error(f"[DATA] Failed to extract biography info: {e}")

# Step 5.1: Extract Plot value
try:
    plot_span = soup.find("span", id="plotValueLabel")
    main_fields["Plot"] = plot_span.get_text(strip=True) if plot_span else ""
except Exception as e:
    log_error(f"[DATA] Failed to extract Plot: {e}")
    main_fields["Plot"] = ""

# Step 6: Extract inscription (if any)
try:
    inscription_section = soup.find("div", class_="inscription")
    main_fields["inscription"] = inscription_section.get_text(strip=True) if inscription_section else ""
except Exception as e:
    log_error(f"[DATA] Failed to extract inscription: {e}")

# Step 7: Extract family info
try:
    family_links = {"parents": [], "spouses": [], "children": []}
    family_section = soup.find("section", id="family-members")

    if family_section:
        for relation in family_links.keys():
            rel_block = family_section.find("div", {"data-relationship": relation})
            if rel_block:
                names = rel_block.find_all("a", href=True)
                family_links[relation] = [a.get_text(strip=True) for a in names]

    main_fields.update({
        "family_parents": ", ".join(family_links["parents"]),
        "family_spouses": ", ".join(family_links["spouses"]),
        "family_children": ", ".join(family_links["children"]),
    })
except Exception as e:
    log_error(f"[DATA] Failed to extract family info: {e}")

# Step 10: Save to Excel without flowers and photos sheets
try:
    main_df = pd.DataFrame([main_fields])
    columns_to_drop = ['inscription', 'family_parents', 'family_spouses', 'family_children']
    main_df = main_df.drop(columns=columns_to_drop, errors='ignore')

    writer = pd.ExcelWriter(OUTPUT_FILE, engine="xlsxwriter")
    main_df.to_excel(writer, index=False, sheet_name="Memorial Info")
    writer.close()

    print(f"✅ Saved to: {os.path.abspath(OUTPUT_FILE)}")
except Exception as e:
    log_error(f"[SAVE] Failed to save Excel: {e}")
    raise SystemExit("Excel save failed. Check errors.txt.")
