from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

def generate_timetable_layout(
        start_time_str: str,
        end_time_str: str,
        breaks: List[Dict[str, str]],
        lecture_duration_minutes: int,
        lab_duration_minutes: int,
        working_days: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
        Generate an empty timetable layout based on time constraints with automatic day generation.

        Args:
            start_time_str: Start time of the timetable (format "HH:MM")
            end_time_str: End time of the timetable (format "HH:MM")
            breaks: List of break periods with "start" and "end" times
            lecture_duration_minutes: Duration of each lecture slot in minutes
            lab_duration_minutes: Duration of each lab slot in minutes
            working_days: Optional list of working days (default: Mon-Sat)

        Returns:
            Dictionary representing the timetable structure with grid and metadata
    """
    if working_days is None:
        working_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    start_time = _parse_time(start_time_str)
    end_time = _parse_time(end_time_str)

    # Validate input times
    if start_time >= end_time:
        raise ValueError("Start time must be before end time")

    break_periods = []
    for br in breaks:
        br_start = _parse_time(br["start"])
        br_end = _parse_time(br["end"])

        if br_start >=  br_end:
            raise ValueError("Start time must be before end time")

        break_periods.append((br_start, br_end, br.get("name", "Break")))

    break_periods.sort(key=lambda x: x[0])
    merged_breaks = _merge_breaks(break_periods)

    slot_duration = _gcd(lecture_duration_minutes, lab_duration_minutes)
    time_slots = _generate_time_slots(start_time, end_time, merged_breaks, slot_duration)

    # Create grid structure
    grid = {}

    for day in working_days:
        grid[day] = {}
        for slot in time_slots:
            slot_key = f"{slot['start']}-{slot['end']}"

            if slot['is_break']:
                grid[day][slot_key] = {
                    "type": "break",
                    "name": slot["break_name"]
                }
            else:
                grid[day][slot_key] = None

    return {
        "layout": {
            "days": working_days,
            "time_slots": time_slots,
            "slot_duration": slot_duration,
            "lecture_slots": lecture_duration_minutes // slot_duration,
            "lab_slots": lab_duration_minutes // slot_duration
        },
        "grid": grid
    }

def _gcd(a: int, b: int) -> int:
    """Calculate greatest common divisor using Euclidean algorithm"""
    while b:
        a, b = b, a % b
    return a

def _generate_time_slots(start_time, end_time, breaks, slot_duration):
    time_slots = []
    current_time = start_time
    breaks_iter = iter(breaks)
    current_break = next(breaks_iter, None)

    while current_time < end_time:
        slot_end = current_time + timedelta(minutes=slot_duration)
        if slot_end > end_time:
            break

        # Check if current slot overlaps with current_break
        if current_break:
            br_start, br_end, br_name = current_break

            if slot_end <= br_start:
                # Slot before break — normal slot
                time_slots.append({"start": _format_time(current_time),
                                   "end": _format_time(slot_end),
                                   "is_break": False})
                current_time = slot_end

            elif current_time >= br_end:
                # Passed current break, get next
                current_break = next(breaks_iter, None)

            else:
                # Slot overlaps break, create break slot
                # Determine break slot start and end within current_time and slot_end
                break_slot_start = max(current_time, br_start)
                break_slot_end = min(slot_end, br_end)
                time_slots.append({
                    "start": _format_time(break_slot_start),
                    "end": _format_time(break_slot_end),
                    "is_break": True,
                    "break_name": br_name
                })

                # Move current_time to end of this break slot
                current_time = break_slot_end

                # If we passed current break completely, get next
                if current_time >= br_end:
                    current_break = next(breaks_iter, None)

        else:
            # No more breaks — normal slot
            time_slots.append({"start": _format_time(current_time),
                               "end": _format_time(slot_end),
                               "is_break": False})
            current_time = slot_end

    return time_slots


def _merge_breaks(break_periods: List[tuple]) -> List[tuple]:
    """Merge overlapping break periods"""
    if not break_periods:
        return []

    merged = []
    current_start, current_end, current_name = break_periods[0]

    for next_start, next_end, next_name in break_periods[1:]:
        if next_start <= current_end:
            current_end = max(current_end, next_end)
            current_name = f"{current_name}, {next_name}"
        else:
            merged.append((current_start, current_end, current_name))
            current_start, current_end, current_name = next_start, next_end, next_name

    merged.append((current_start, current_end, current_name))
    return merged

def _parse_time(time_str: str) -> datetime:
    """Parse time string (HH:MM or HHMM) into datetime object"""
    try:
        return datetime.strptime(time_str, "%H:%M")
    except ValueError:
        try:
            return datetime.strptime(time_str, "%H%M")
        except ValueError:
            if len(time_str) == 3:
                return datetime.strptime("0" + time_str, "%H%M")
            raise ValueError(f"Invalid time string {time_str}")

def _format_time(dt: datetime) -> str:
    """Format datetime object into HH:MM format"""
    return dt.strftime("%H:%M")