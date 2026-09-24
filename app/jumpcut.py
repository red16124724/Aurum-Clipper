from typing import List, Tuple, Dict, Any
import copy

def calculate_segments(words: List[Dict[str, Any]], clip_start: float, clip_end: float, max_silence: float = 0.6, pad: float = 0.15) -> List[Tuple[float, float]]:
    """
    Calculate the 'keep' segments by finding silent gaps between words.
    Returns segments in the ORIGINAL timeline.
    """
    if not words:
        return [(clip_start, clip_end)]
    
    keep_segments = []
    
    # We pad the spoken words slightly so it doesn't sound unnaturally chopped
    current_start = max(clip_start, words[0]['start'] - pad)
    current_end = words[0]['end'] + pad
    
    for i in range(1, len(words)):
        w = words[i]
        w_start = w['start'] - pad
        w_end = w['end'] + pad
        
        gap = w_start - current_end
        if gap > max_silence:
            # The gap is long enough to cut! Commit the current segment.
            keep_segments.append((max(clip_start, current_start), min(clip_end, current_end)))
            current_start = w_start
            current_end = w_end
        else:
            # Merge into the current segment
            current_end = max(current_end, w_end)
            
    # Commit the last segment
    keep_segments.append((max(clip_start, current_start), min(clip_end, current_end)))
    return keep_segments


def _map_time_to_jumpcut(t_abs: float, keep_segments: List[Tuple[float, float]]) -> float:
    """Project an absolute timestamp onto the compressed timeline created by keep_segments."""
    if not keep_segments:
        return 0.0
    if t_abs <= keep_segments[0][0]:
        return 0.0

    new_t = 0.0
    for s_start, s_end in keep_segments:
        if t_abs < s_start:
            break
        if t_abs <= s_end:
            new_t += (t_abs - s_start)
            return new_t
        new_t += (s_end - s_start)
    return new_t


def remap_words(words: List[Dict[str, Any]], keep_segments: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
    """
    Shifts the word timestamps to match the compressed timeline created by keep_segments.
    Preserves word duration while removing silent gaps.
    """
    if not keep_segments or not words:
        return words

    base_offset = keep_segments[0][0]
    remapped = []

    for w in words:
        w_copy = copy.deepcopy(w)
        dur = max(0.01, w['end'] - w['start'])
        new_start = _map_time_to_jumpcut(w['start'], keep_segments)
        w_copy['start'] = base_offset + new_start
        w_copy['end'] = base_offset + new_start + dur
        remapped.append(w_copy)

    return remapped


def remap_keyframes(keyframes: List[Dict[str, Any]], keep_segments: List[Tuple[float, float]], clip_start: float = 0.0) -> List[Dict[str, Any]]:
    """
    Shifts keyframe timestamps (e.g. tracking keyframes with 'time' or 't') to match
    the compressed timeline created by keep_segments.
    """
    if not keep_segments or not keyframes:
        return keyframes

    remapped = []
    for kf in keyframes:
        kf_copy = copy.deepcopy(kf)
        t = float(kf_copy.get("time", kf_copy.get("t", 0.0)))
        # Keyframes from tracker are relative to clip_start
        t_abs = clip_start + t
        new_t = _map_time_to_jumpcut(t_abs, keep_segments)

        if "time" in kf_copy:
            kf_copy["time"] = round(new_t, 3)
        if "t" in kf_copy:
            kf_copy["t"] = round(new_t, 3)
        remapped.append(kf_copy)

    return remapped
