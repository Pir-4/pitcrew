from pitcrew.clients.links import WebLinks


def test_test_cases_link_searches_exactly_these_test_cases(links: WebLinks) -> None:
    url = links.test_cases(3, [106459, 89663, 100830])

    # The search is `[{"id":"aql","type":"string","value":"id in [89663, 100830, 106459]"}]`
    # in base64, its `=` padding URL-encoded: the ids sorted.
    assert url == (
        "https://testops.example/project/3/test-cases?search="
        "W3siaWQiOiJhcWwiLCJ0eXBlIjoic3RyaW5nIiwidmFsdWUiOiJpZCBpbiBbODk2NjMsIDEwMDgz"
        "MCwgMTA2NDU5XSJ9XQ%3D%3D"
    )
