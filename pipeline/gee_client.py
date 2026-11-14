"""NASA climate access. Backend 1 owns this file.
"""
GEE_COLLECTIONS = {
    "gldas": "NASA/GLDAS/V021/NOAH/G025/T3H",
    "imerg": "NASA/GPM_L3/IMERG_V06",
    "smap_usda": "NASA_USDA/HSL/SMAP10KM_soil_moisture",
}


def get_nasa_climate_summary(region: str) -> dict:
    raise NotImplementedError("Backend 1: implement cached NASA climate summary")
