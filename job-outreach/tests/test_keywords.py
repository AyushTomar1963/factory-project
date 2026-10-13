from jobhunt import keywords


def test_extract_canonicalises_aliases_and_orders_by_position():
    text = "We run Postgres and k8s. Golang preferred; some ReactJS."
    assert keywords.extract(text) == ["PostgreSQL", "Kubernetes", "Go", "React"]


def test_short_terms_are_case_sensitive():
    assert "Go" not in keywords.extract("we go to market fast")
    assert "Go" in keywords.extract("services written in Go")
    assert "R" not in keywords.extract("r and d")


def test_cpp_and_csharp_boundaries():
    assert keywords.extract("C++ and C# experience") == ["C++", "C#"]


def test_match_score():
    assert keywords.match_score(["Python", "Rust", "Go", "SQL"], {"Python", "Go"}) == 0.5
    assert keywords.match_score(["Python"], {"Python"}) == 0.25
    assert keywords.match_score([], {"Python"}) == 0.0


def test_numbers():
    assert keywords.numbers("cut costs by 30% for 2M users in 4,000 rps") == {"30%", "2m", "4,000"}
