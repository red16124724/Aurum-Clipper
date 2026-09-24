import logging

logger = logging.getLogger(__name__)

TEMPLATES = {
    "sigma_grindset": {
        "description": "High contrast, dramatic vibe. Best for motivational speeches, tough talk, or intense moments.",
        "overrides": {
            "fit_mode": "static_split",
            "caption_style": "hormozi_yellow",
            "cinematic": {
                "color_grade": "high_contrast",
                "vignette": True,
                "vignette_strength": 70,
                "grain": True,
                "grain_strength": 60,
                "sharpen": True
            }
        }
    },
    "storytime_chill": {
        "description": "Soft, engaging, friendly vibe. Best for personal stories, casual talks, or vlogs.",
        "overrides": {
            "fit_mode": "dynamic_split",
            "caption_style": "bold_white",
            "cinematic": {
                "color_grade": "warm",
                "glow": True,
                "glow_strength": 40,
                "top_gradient": True
            }
        }
    },
    "podcast_classic": {
        "description": "Clean, standard, professional vibe. Best for educational content, interviews, or news.",
        "overrides": {
            "fit_mode": "crop",
            "caption_style": "raj_clean",
            "cinematic": {
                "color_grade": "none",
                "sharpen": True,
                "sharpen_strength": 50,
                "bottom_gradient": True,
                "bottom_gradient_strength": 80
            }
        }
    },
    "hype_beast": {
        "description": "Loud, colorful, highly animated. Best for high-energy reactions, gaming, or pranks.",
        "overrides": {
            "fit_mode": "crop",
            "caption_style": "beast_red",
            "cinematic": {
                "color_grade": "vibrant",
                "glow": True,
                "glow_strength": 70,
                "chroma_shift": True,
                "chroma_shift_strength": 60
            }
        }
    }
}

def get_template(name: str) -> dict:
    if name not in TEMPLATES:
        return {}
    return TEMPLATES[name]["overrides"]
