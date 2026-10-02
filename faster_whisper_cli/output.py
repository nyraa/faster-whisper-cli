"""Writers for Whisper-compatible transcription output formats."""

import json
import os
from dataclasses import asdict, is_dataclass


def _value(segment, name):
    if isinstance(segment, dict):
        return segment[name]
    return getattr(segment, name)


def _text(segment):
    return _value(segment, "text").strip()


def _format_seconds(seconds, decimal_marker):
    # Match the linked converter: timestamps use millisecond precision.
    whole_seconds = int(seconds)
    milliseconds = int((seconds - whole_seconds) * 1000)
    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    seconds = whole_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{decimal_marker}{milliseconds:03d}"


def _segment_dict(segment):
    if isinstance(segment, dict):
        value = segment
    elif is_dataclass(segment):
        value = asdict(segment)
    elif hasattr(segment, "_asdict"):
        value = segment._asdict()
    else:
        value = {
            name: getattr(segment, name)
            for name in ("id", "seek", "start", "end", "text", "tokens",
                         "avg_logprob", "compression_ratio", "no_speech_prob",
                         "words")
            if hasattr(segment, name)
        }
    return _json_value(value)


def _json_value(value):
    if is_dataclass(value):
        return _json_value(asdict(value))
    if hasattr(value, "_asdict"):
        return _json_value(value._asdict())
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _write_txt(segments, file):
    for segment in segments:
        file.write(f"{_text(segment)}\n")


def _write_vtt(segments, file):
    file.write("WEBVTT\n\n")
    for segment in segments:
        start = _format_seconds(_value(segment, "start"), ".")
        end = _format_seconds(_value(segment, "end"), ".")
        file.write(f"{start} --> {end}\n{_text(segment)}\n\n")


def _write_srt(segments, file):
    for index, segment in enumerate(segments, 1):
        start = _format_seconds(_value(segment, "start"), ",")
        end = _format_seconds(_value(segment, "end"), ",")
        file.write(f"{index}\n{start} --> {end}\n{_text(segment)}\n\n")


def _write_tsv(segments, file):
    file.write("start\tend\ttext\n")
    for segment in segments:
        start = round(1000 * _value(segment, "start"))
        end = round(1000 * _value(segment, "end"))
        file.write(f"{start}\t{end}\t{_text(segment).replace(chr(9), ' ')}\n")


def _write_json(segments, language, file):
    result = {
        "text": "".join(_value(segment, "text") for segment in segments).strip(),
        "segments": [_segment_dict(segment) for segment in segments],
        "language": language,
    }
    json.dump(result, file)


_WRITERS = {
    "txt": _write_txt,
    "vtt": _write_vtt,
    "srt": _write_srt,
    "tsv": _write_tsv,
}


def write_outputs(segments, language, audio_path, output, output_format):
    """Write one or all supported formats and return the created paths."""
    segments = list(segments)
    formats = ["txt", "vtt", "srt", "tsv", "json"] if output_format == "all" else [output_format]
    base = output or os.path.splitext(audio_path)[0] + "." + formats[0]
    output_paths = []

    for format_name in formats:
        path = base if output and len(formats) == 1 else os.path.splitext(base)[0] + "." + format_name
        with open(path, "w", encoding="utf-8") as file:
            if format_name == "json":
                _write_json(segments, language, file)
            else:
                _WRITERS[format_name](segments, file)
        output_paths.append(path)
    return output_paths
