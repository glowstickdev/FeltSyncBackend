import csv
import io


class CSVValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(errors))


# ─────────────────────────────────────────────
# MONTHLY TOURNAMENT CSV
# Expected columns (from poker software export):
#   Rank, Nickname, Points, ..., Hits, ...
# ─────────────────────────────────────────────

MONTHLY_REQUIRED_COLS = {"Nickname", "Points"}


def validate_and_parse_csv(csv_file):
    """
    Parse a monthly tournament CSV.
    Returns list of dicts: {player_name, score, knockouts}
    """
    errors = []

    try:
        raw = csv_file.read()
        text = raw.decode("utf-8-sig")  # handles BOM
    except Exception as e:
        raise CSVValidationError([f"Could not read file: {e}"])

    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])

    missing = MONTHLY_REQUIRED_COLS - headers
    if missing:
        raise CSVValidationError([
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Found: {', '.join(sorted(headers))}"
        ])

    rows = []
    for i, row in enumerate(reader, start=2):
        nickname = (row.get("Nickname") or "").strip()
        if not nickname:
            errors.append(f"Row {i}: Empty nickname, skipping.")
            continue

        raw_points = (row.get("Points") or "").strip()
        try:
            score = float(raw_points)
        except ValueError:
            errors.append(f"Row {i} ({nickname}): Invalid points value '{raw_points}'.")
            continue

        # Knockouts / Hits column — optional, default 0
        raw_hits = (row.get("Hits") or row.get("hits") or "0").strip()
        try:
            knockouts = int(float(raw_hits))
        except ValueError:
            knockouts = 0

        raw_rank = (row.get("Rank") or row.get("rank") or "").strip()
        try:
            rank = int(float(raw_rank)) if raw_rank else None
        except ValueError:
            rank = None

        rows.append({
            "player_name": nickname,
            "score": score,
            "rank": rank,
            "knockouts": knockouts,
        })

    if errors and not rows:
        raise CSVValidationError(errors)

    if not rows:
        raise CSVValidationError(["No valid rows found in the CSV."])

    return rows, errors  # return warnings alongside data


# ─────────────────────────────────────────────
# OVERALL / YEAR-TO-DATE CSV
# Expected columns:
#   #, Name, Points, Games Played, EOY Pool, Knockouts, Nickname
# ─────────────────────────────────────────────

OVERALL_REQUIRED_COLS = {"Name", "Games Played", "EOY Pool"}


def validate_and_parse_overall_csv(csv_file):
    """
    Parse the overall/YTD stats CSV.
    Returns list of dicts: {player_name, games_played, eoy_pool, total_knockouts}
    """
    errors = []

    try:
        raw = csv_file.read()
        text = raw.decode("utf-8-sig")
    except Exception as e:
        raise CSVValidationError([f"Could not read file: {e}"])

    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])

    missing = OVERALL_REQUIRED_COLS - headers
    if missing:
        raise CSVValidationError([
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Found: {', '.join(sorted(headers))}"
        ])

    rows = []
    for i, row in enumerate(reader, start=2):
        # Use Nickname if present and non-empty, otherwise fall back to Name
        nickname = (row.get("Nickname") or "").strip()
        name = (row.get("Name") or "").strip()
        player_name = nickname if nickname else name
        if not player_name:
            errors.append(f"Row {i}: No name found, skipping.")
            continue

        raw_games = (row.get("Games Played") or "0").strip()
        try:
            games_played = int(float(raw_games))
        except ValueError:
            games_played = 0

        raw_eoy = (row.get("EOY Pool") or "0").strip().replace("$", "").replace(",", "")
        try:
            eoy_pool = float(raw_eoy)
        except ValueError:
            eoy_pool = 0.0

        raw_ko = (row.get("Knockouts") or row.get("knockouts") or "0").strip()
        try:
            total_knockouts = int(float(raw_ko))
        except ValueError:
            total_knockouts = 0

        rows.append({
            "player_name": player_name,
            "games_played": games_played,
            "eoy_pool": eoy_pool,
            "total_knockouts": total_knockouts,
        })

    if not rows:
        raise CSVValidationError(["No valid rows found in the overall CSV."])

    return rows, errors
