import base64
import pytest
from app.core.storage import storage


def test_upload_base64_data_url_passthrough():
    # Regular HTTP/HTTPS URL should be returned as-is
    url = "https://images.unsplash.com/photo-1610030469983-98e550d6193c"
    assert storage.upload_base64_data_url(url) == url

    # Empty or None should return empty
    assert storage.upload_base64_data_url("") == ""
    assert storage.upload_base64_data_url(None) == ""


def test_upload_base64_data_url_conversion():
    # 1x1 transparent PNG data URL
    png_data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    converted_url = storage.upload_base64_data_url(png_data_url, folder="products")
    
    assert converted_url is not None
    assert not converted_url.startswith("data:")
    assert "products/" in converted_url
    assert converted_url.endswith(".png")

