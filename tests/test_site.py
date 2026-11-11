from bvb.site import dest_slug


def test_dest_slug():
    assert dest_slug("São Paulo", "SAO") == "sao-paulo-sao"
    assert dest_slug("San José", "SJO") != dest_slug("San José", "SJC")
    assert dest_slug("", "MAD") == "mad"


def test_card_image():
    from bvb.site import card_image
    a, b = card_image("https://images.unsplash.com/photo-1?auto=format&fit=crop&w=800&q=70")
    assert a.endswith("&w=400&h=190") and b.endswith("&w=800&h=380") and a.count("?") == 1
    assert card_image("https://otro.com/x.jpg") == ("https://otro.com/x.jpg", "")
    assert card_image("") == ("", "")
