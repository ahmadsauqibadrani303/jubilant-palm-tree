"""
Fertilizer and amendment advice configuration for SAFRONS.
Adheres strictly to the hard rule: quantitative dosages default to None + TODO(expert).
Qualitative advisory text is provided when quantitative dosage is None.
"""

from typing import Any

DEFAULT_QUALITATIVE_DOSAGE_NOTE = "Dosis ditentukan setelah uji tanah/arahan penyuluh"

# Configuration dictionary for amendments per soil constraint
# Dosages are explicitly None pending local agronomist laboratory calibration.
AMENDMENT_RULES: dict[str, dict[str, Any]] = {
    "ph_acid": {
        "parameter": "ph",
        "action_type": "pengapuran",
        "title": "Pengapuran Tanah Masam",
        "input_category": "Kapur Pertanian (Dolomit / Kaptan)",
        "recommendation": (
            "Aplikasi kapur pertanian (dolomit atau kalsit) untuk menaikkan pH tanah "
            "dan menekan kejenuhan aluminium toksik."
        ),
        # TODO(expert): Fill quantitative dosage (kg/ha or ton/ha) based on exchangeable Al / buffer curve
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "Reaksi tanah masam menghambat ketersediaan hara makro (terutama P) dan meningkatkan risiko keracunan Al.",
    },
    "ph_alkaline": {
        "parameter": "ph",
        "action_type": "penurunan_ph",
        "title": "Pengelolaan Tanah Basa",
        "input_category": "Bahan Organik / Belerang Pertanian",
        "recommendation": (
            "Aplikasi bahan organik matang (kompos/pupuk kandang) atau pupuk pembentuk asam (seperti ZA) "
            "untuk menurunkan pH tanah secara bertahap."
        ),
        # TODO(expert): Calibrate dosage for alkaline mitigation
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "pH tinggi menurunkan ketersediaan hara mikro seperti Fe, Mn, Zn.",
    },
    "n_low": {
        "parameter": "n_rata2",
        "action_type": "pemupukan_n",
        "title": "Pemupukan Sumber Nitrogen",
        "input_category": "Pupuk Nitrogen (Urea / ZA / Kompos)",
        "recommendation": (
            "Aplikasi pupuk sumber N secara bertahap (split application) bersama bahan organik "
            "untuk mendukung pertumbuhan vegetatif dan pembentukan klorofil."
        ),
        # TODO(expert): Fill recommended dosage based on crop target
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "Kadar N rendah menyebabkan pertumbuhan kerdil dan daun menguning (klorosis).",
    },
    "n_high": {
        "parameter": "n_rata2",
        "action_type": "efisiensi_n",
        "title": "Efisiensi dan Pengurangan Input Nitrogen",
        "input_category": "Pengurangan Takaran Pupuk N",
        "recommendation": (
            "Kurangi aplikasi pupuk N anorganik untuk mencegah sukulensi berlebih, "
            "rebah tanaman, dan kerentanan terhadap serangan hama/penyakit."
        ),
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "Kadar N sudah berada di pita atas; penambahan berlebih berisiko mencemari air tanah dan memboroskan biaya.",
    },
    "p_low": {
        "parameter": "p_rata2",
        "action_type": "pemupukan_p",
        "title": "Pemupukan Sumber Fosfor",
        "input_category": "Pupuk Fosfat (SP-36 / Rock Phosphate)",
        "recommendation": (
            "Aplikasi pupuk fosfat sebagai pupuk dasar saat tanam pada zona perakaran "
            "untuk memacu pertumbuhan perakaran dan pembungaan."
        ),
        # TODO(expert): Calibrate SP-36 dosage
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "Kadar P rendah membatasi perkembangan sistem perakaran dan inisiasi bunga/buah.",
    },
    "p_high": {
        "parameter": "p_rata2",
        "action_type": "efisiensi_p",
        "title": "Pemantauan Status Fosfor",
        "input_category": "Pengurangan Pupuk P",
        "recommendation": (
            "Pertahankan input P pada tingkat pemeliharaan (maintenance); hindari penambahan pupuk P dosis tinggi."
        ),
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "Kadar P tanah relatif tinggi; akumulasi berlebih dapat mengikat seng (Zn) dan besi (Fe).",
    },
    "k_low": {
        "parameter": "k_rata2",
        "action_type": "pemupukan_k",
        "title": "Pemupukan Sumber Kalium",
        "input_category": "Pupuk Kalium (KCl / ZK / Abu Janjang)",
        "recommendation": (
            "Aplikasi pupuk kalium untuk memperkuat dinding sel tanaman, meningkatkan translokasi asimilat, "
            "serta ketahanan tanaman terhadap kekeringan dan hama."
        ),
        # TODO(expert): Calibrate KCl dosage
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "Kadar K rendah melemahkan daya tahan tanaman terhadap rebah dan stres abiotik.",
    },
    "k_high": {
        "parameter": "k_rata2",
        "action_type": "efisiensi_k",
        "title": "Pemantauan Status Kalium",
        "input_category": "Pemeliharaan K",
        "recommendation": (
            "Kurangi takaran pupuk kalium; prioritaskan keseimbangan kation Ca dan Mg."
        ),
        "dosage": None,
        "dosage_note": DEFAULT_QUALITATIVE_DOSAGE_NOTE,
        "reason": "Kadar K tinggi dapat menyebabkan antagonisme serapan magnesium (Mg) dan kalsium (Ca).",
    },
    "slope_steep": {
        "parameter": "slope",
        "action_type": "konservasi_lahan",
        "title": "Konservasi Tanah & Air Lereng Curam",
        "input_category": "Terasering / Guludan / Tanaman Penutup (Cover Crop)",
        "recommendation": (
            "Terapkan teknik konservasi tanah mekanis (teras bangku/gulud) dan vegetatif "
            "(penanaman rumput vetiver atau legum penutup tanah) sebelum intensifikasi budidaya."
        ),
        "dosage": None,
        "dosage_note": "Sesuaikan rancangan teras dengan kemiringan dan arahan penyuluh",
        "reason": "Kemiringan lereng curam meningkatkan laju aliran permukaan dan erosi hara lapisan olah tanah.",
    },
}


def get_amendment_for_factor(key: str, status: str, severity: str) -> dict[str, Any] | None:
    """
    Look up amendment advice for a diagnostic factor.
    Returns None if no action is required (e.g. status is neutral or optimal).
    """
    if key == "ph":
        if status in {"very_acid", "acid"}:
            return AMENDMENT_RULES["ph_acid"]
        if status in {"slightly_alkaline", "alkaline"}:
            return AMENDMENT_RULES["ph_alkaline"]
    elif key == "n_rata2":
        if status in {"very_low", "low"}:
            return AMENDMENT_RULES["n_low"]
        if status in {"high", "very_high"}:
            return AMENDMENT_RULES["n_high"]
    elif key == "p_rata2":
        if status in {"very_low", "low"}:
            return AMENDMENT_RULES["p_low"]
        if status in {"high", "very_high"}:
            return AMENDMENT_RULES["p_high"]
    elif key == "k_rata2":
        if status in {"very_low", "low"}:
            return AMENDMENT_RULES["k_low"]
        if status in {"high", "very_high"}:
            return AMENDMENT_RULES["k_high"]
    elif key == "slope" and status in {"steep", "very_steep"}:
        return AMENDMENT_RULES["slope_steep"]

    return None
