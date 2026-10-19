from __future__ import annotations

from pathlib import Path
import tempfile

import pytest
from pytest_bdd import given, scenarios, then, when
from PIL import Image

from src.integrations import image_cascade
from src.integrations.huggingface import client as huggingface_client


scenarios("tee_image_provider_authorization.feature")


@given(
    "the Fal Krea route is mocked and temporary output is available",
    target_fixture="probe_context",
)
def mocked_fal_probe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    context: dict[str, object] = {"calls": [], "fail": False, "tmp_path": tmp_path}

    class FakeInferenceClient:
        def __init__(
            self, *, model: str, provider: str, token: str, timeout: float
        ) -> None:
            pass

        def text_to_image(
            self,
            prompt: str,
            *,
            width: int,
            height: int,
            negative_prompt: str | None,
            seed: int,
        ) -> Image.Image:
            calls = context["calls"]
            assert isinstance(calls, list)
            calls.append((width, height))
            if context["fail"]:
                raise RuntimeError("synthetic Fal failure")
            return Image.new("RGB", (width, height), "black")

    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    monkeypatch.setattr(huggingface_client, "InferenceClient", FakeInferenceClient)
    context["cascade_factory"] = getattr(image_cascade, "tee_image_cascade", None)
    return context


@when("the route is called once at 512 by 512 and then tested for failure")
def call_fal_probe_and_failure(probe_context: dict[str, object]) -> None:
    factory = probe_context["cascade_factory"]
    assert callable(factory), "the tee-specific authorization cascade is missing"
    tmp_path = probe_context["tmp_path"]
    assert isinstance(tmp_path, Path)
    with tempfile.TemporaryDirectory(dir=tmp_path) as temporary_dir:
        result = factory(image_size="512x512").generate(
            "one-shot route probe", output_dir=Path(temporary_dir)
        )
        probe_context["successful_output"] = result.path
        probe_context["successful_temp_dir"] = Path(temporary_dir)
    success_calls = probe_context["calls"]
    assert isinstance(success_calls, list)
    probe_context["success_calls"] = list(success_calls)
    success_calls.clear()
    probe_context["fail"] = True
    with tempfile.TemporaryDirectory(dir=tmp_path) as temporary_dir:
        with pytest.raises(RuntimeError, match="No authorized route remains"):
            factory(image_size="512x512").generate(
                "one-shot route probe", output_dir=Path(temporary_dir)
            )
        probe_context["failed_temp_dir"] = Path(temporary_dir)
    probe_context["failed_calls"] = list(success_calls)


@then("successful output stays temporary and the failed request is not retried")
def assert_single_temporary_fal_probe(probe_context: dict[str, object]) -> None:
    successful_output = probe_context["successful_output"]
    successful_temp_dir = probe_context["successful_temp_dir"]
    failed_temp_dir = probe_context["failed_temp_dir"]
    assert isinstance(successful_output, Path)
    assert isinstance(successful_temp_dir, Path)
    assert isinstance(failed_temp_dir, Path)
    assert successful_output.parent == successful_temp_dir
    assert not successful_output.exists()
    assert not successful_temp_dir.exists()
    assert not failed_temp_dir.exists()
    assert probe_context["success_calls"] == [(512, 512)]
    assert probe_context["failed_calls"] == [(512, 512)]


@given(
    "tee generation starts with OpenAI disabled and only Fal Krea authorized",
    target_fixture="provider_context",
)
def default_tee_provider_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    monkeypatch.delenv("TEE_IMAGE_OPENAI_ENABLED", raising=False)
    return _provider_context(monkeypatch, tmp_path)


@given(
    "Fal Krea is the only authorized route and Pollinations remains unverified",
    target_fixture="provider_context",
)
def failing_fal_provider_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    context = _provider_context(monkeypatch, tmp_path)
    context["fal_fails"] = True
    return context


@given(
    "the OpenAI toggle is enabled but its exact route is not allowlisted",
    target_fixture="provider_context",
)
def enabled_unlisted_openai_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    monkeypatch.setenv("TEE_IMAGE_OPENAI_ENABLED", "true")
    return _provider_context(monkeypatch, tmp_path)


def _provider_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    context: dict[str, object] = {"calls": [], "fal_fails": False}

    class FakeOpenAI:
        def generate_image(self, prompt: str, *, output_dir: Path | None) -> Path:
            calls = context["calls"]
            assert isinstance(calls, list)
            calls.append(("openai", "gpt-image-1"))
            return _write_image(tmp_path, "openai")

    class FakeFalKrea:
        def generate_image(
            self, prompt: str, *, output_dir: Path | None, **kwargs: object
        ) -> Path:
            calls = context["calls"]
            assert isinstance(calls, list)
            calls.append(("fal-ai", "black-forest-labs/FLUX.1-Krea-dev"))
            if context["fal_fails"]:
                raise RuntimeError("Fal Krea unavailable")
            return _write_image(tmp_path, "fal-krea")

    class FakePollinations:
        def generate_image(self, prompt: str, *, output_dir: Path | None) -> Path:
            calls = context["calls"]
            assert isinstance(calls, list)
            calls.append(("pollinations", "default"))
            return _write_image(tmp_path, "pollinations")

    monkeypatch.setattr("src.integrations.dalle3.client.DallE3Client", FakeOpenAI)
    monkeypatch.setattr(
        "src.integrations.huggingface.client.HuggingFaceImageClient", FakeFalKrea
    )
    monkeypatch.setattr(
        "src.integrations.pollinations.client.PollinationsClient", FakePollinations
    )
    context["cascade_factory"] = getattr(image_cascade, "tee_image_cascade", None)
    return context


def _write_image(directory: Path, name: str) -> Path:
    path = directory / f"{name}.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    return path


@when("the tee cascade generates an image")
def generate_with_default_tee_cascade(provider_context: dict[str, object]) -> None:
    factory = provider_context["cascade_factory"]
    assert callable(factory), "the tee-specific authorization cascade is missing"
    provider_context["result"] = factory().generate("tee artwork")


@when("Fal Krea fails during tee generation")
def generate_after_fal_failure(provider_context: dict[str, object]) -> None:
    factory = provider_context["cascade_factory"]
    assert callable(factory), "the tee-specific authorization cascade is missing"
    try:
        provider_context["result"] = factory().generate("tee artwork")
    except Exception as exc:
        provider_context["error"] = exc


@when("tee generation runs before and after that exact route is allowlisted")
def run_openai_route_gate(
    provider_context: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = provider_context["cascade_factory"]
    assert callable(factory), "the tee-specific authorization cascade is missing"
    factory().generate("tee artwork")
    unlisted_calls = provider_context["calls"]
    assert isinstance(unlisted_calls, list)
    provider_context["unlisted_calls"] = list(unlisted_calls)
    unlisted_calls.clear()
    monkeypatch.setattr(
        image_cascade,
        "TEE_IMAGE_AUTHORIZATION_ALLOWLIST",
        frozenset(
            {
                ("fal-ai", "black-forest-labs/FLUX.1-Krea-dev", "fal-ai/flux/krea"),
                ("openai", "gpt-image-1", "openai/images/generations"),
            }
        ),
        raising=False,
    )
    provider_context["allowlisted_result"] = factory().generate("tee artwork")


@then("only the Fal Krea route is attempted and its provider and model are returned")
def assert_only_fal_route(provider_context: dict[str, object]) -> None:
    assert provider_context["calls"] == [
        ("fal-ai", "black-forest-labs/FLUX.1-Krea-dev")
    ]
    result = provider_context["result"]
    assert result is not None
    assert (result.provider, result.model, result.route) == (
        "fal-ai",
        "black-forest-labs/FLUX.1-Krea-dev",
        "fal-ai/flux/krea",
    )


@then("Pollinations is skipped and the error reports no authorized route remains")
def assert_no_unverified_fallback(provider_context: dict[str, object]) -> None:
    error = provider_context["error"]
    assert provider_context["calls"] == [
        ("fal-ai", "black-forest-labs/FLUX.1-Krea-dev")
    ]
    assert isinstance(error, RuntimeError)
    assert "no authorized route remains" in str(error).lower()
    assert [(item.provider, item.model) for item in error.diagnostics] == [
        ("fal-ai", "black-forest-labs/FLUX.1-Krea-dev")
    ]


@then(
    "OpenAI is skipped first and eligible in provider order only after allowlisting"
)
def assert_openai_requires_allowlist(provider_context: dict[str, object]) -> None:
    assert provider_context["unlisted_calls"] == [
        ("fal-ai", "black-forest-labs/FLUX.1-Krea-dev")
    ]
    assert provider_context["calls"] == [("openai", "gpt-image-1")]
    result = provider_context["allowlisted_result"]
    assert (result.provider, result.model) == ("openai", "gpt-image-1")