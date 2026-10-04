"""STT fragments belonging to one spoken utterance must reach the agent whole.

Sarvam's VAD can split a sentence into several "final" transcripts. Dispatching
each one made the agent answer a fragment, and the router's barge-in cancelled
that answer when the next fragment arrived — so the start of the sentence was
never handled.
"""

import asyncio

import pytest

from customagents.voiceagent.utterance import UtteranceCoalescer


def test_merge_appends_separate_fragments():
    assert (
        UtteranceCoalescer.merge("I have a headache", "and a fever")
        == "I have a headache and a fever"
    )


def test_merge_replaces_cumulative_transcripts():
    # Some engines resend the whole transcript so far rather than a delta.
    assert UtteranceCoalescer.merge("My name is", "My name is Suno") == "My name is Suno"


def test_merge_ignores_a_repeated_tail():
    assert UtteranceCoalescer.merge("My name is Suno", "Suno") == "My name is Suno"


def test_merge_handles_empty_buffer():
    assert UtteranceCoalescer.merge("", "hello") == "hello"


async def _next_utterance(coalescer, timeout=1.0):
    return await asyncio.wait_for(coalescer.utterances().__anext__(), timeout=timeout)


@pytest.mark.asyncio
async def test_fragments_inside_the_window_arrive_as_one_utterance():
    coalescer = UtteranceCoalescer(silence_seconds=0.2)

    coalescer.add("I have a headache", "en-IN")
    await asyncio.sleep(0.05)
    coalescer.add("and a fever", "en-IN")

    text, language = await _next_utterance(coalescer)

    assert text == "I have a headache and a fever"
    assert language == "en-IN"
    coalescer.close()


@pytest.mark.asyncio
async def test_a_single_utterance_is_released_after_the_silence_window():
    coalescer = UtteranceCoalescer(silence_seconds=0.05)
    coalescer.add("hello there", "en-IN")

    text, _ = await _next_utterance(coalescer)

    assert text == "hello there"
    coalescer.close()


@pytest.mark.asyncio
async def test_fragments_split_by_a_long_pause_stay_separate():
    coalescer = UtteranceCoalescer(silence_seconds=0.05)

    coalescer.add("first sentence", "en-IN")
    first, _ = await _next_utterance(coalescer)

    coalescer.add("second sentence", "en-IN")
    second, _ = await _next_utterance(coalescer)

    assert first == "first sentence"
    assert second == "second sentence"
    coalescer.close()


@pytest.mark.asyncio
async def test_blank_fragments_are_ignored():
    coalescer = UtteranceCoalescer(silence_seconds=0.05)
    coalescer.add("   ", "en-IN")
    coalescer.add("real words", "en-IN")

    text, _ = await _next_utterance(coalescer)

    assert text == "real words"
    coalescer.close()
