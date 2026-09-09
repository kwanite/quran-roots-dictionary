# Data Sources

This application includes a bundled SQLite database containing classical Arabic lexical data and Qur’anic text. All included materials are either in the public domain due to their age or derived from public domain sources.

## Dictionaries

The following dictionaries are included:

- **Lisān al-ʿArab** (ابن منظور, d. 1311)
- **Al-Ṣiḥāḥ** (الجوهري, d. 1002)
- **Maqāyīs al-Lugha** (ابن فارس, d. 1004)
- **Al-Muḥīṭ** (الفيروزآبادي, d. 1414)
- **Tāj al-ʿArūs** (الزبيدي, d. 1791) *(if included via mujamul_ghoni or related datasets)*
- **Al-Muʿjam al-Wasīṭ** (مجمع اللغة العربية, 20th century — see note below)
- **Al-Muʿjam al-Muʿāṣir** (modern dictionary — see note below)
- **Mufradāt Alfāẓ al-Qurʾān** (الراغب الأصفهاني, d. 1108)
- **Lane’s Lexicon** (Edward William Lane, d. 1876)

## Licensing Notes

- Classical works (e.g., Lisān al-ʿArab, Al-Ṣiḥāḥ, Maqāyīs al-Lugha, etc.) are **public domain** due to the expiration of copyright.
- Lane’s Lexicon is also **public domain**.

### Important Clarification

Some included datasets (e.g., *Al-Muʿjam al-Wasīṭ* and *Al-Muʿjam al-Muʿāṣir*) are **modern works**. The data included here is sourced from publicly available digital texts. No proprietary formatting, annotations, or restricted editions are intentionally included.

## Data Processing

- Data has been normalized and structured into a SQLite database.
- Some entries include simplified forms (e.g., removal of harakat).
- Relationships (e.g., root-based grouping) were added programmatically.

## No Proprietary Sources

This project does **not** include:
- Proprietary dictionary databases
- Paid or restricted datasets

All efforts have been made to ensure that included data complies with open distribution requirements.

---

If any data source is found to violate licensing terms, please open an issue:
https://github.com/wizsk/arabic_lexicons/issues
