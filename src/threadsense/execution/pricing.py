"""Provider list prices (USD per token) for the exact models used by full runs, and the conservative reservation.

Rates were checked on 2026-11-05 against the provider pricing page (developers.openai.com/api/docs/pricing) and the
prompt-caching guide, and agree with LiteLLM's bundled local cost map (tests compare them). Standard (synchronous)
rates apply: no batch discount is assumed. Cache reads are a discount and are never assumed when reserving. GPT-5.6 and
later bill cache writes automatically at 1.25x input for the default 30-minute lifetime (12-hour writes need an explicit
option these requests never set), so their input is reserved at the write rate. Direct API billing adds no
credit-purchase fee; FEE_RATE stays an explicit setting.
"""
import json

VERIFIED = '2026-11-05: developers.openai.com/api/docs/pricing and guides/prompt-caching'
FEE_RATE = 0.0
# Body model name -> rates. cache_write is None where the provider lists no cache-write charge.
PRICES = {
    'gpt-4o-mini-2024-07-18': {'input': 0.15e-6, 'cached_input': 0.075e-6, 'cache_write': None, 'output': 0.60e-6},
    'gpt-4o-mini': {'input': 0.15e-6, 'cached_input': 0.075e-6, 'cache_write': None, 'output': 0.60e-6},
    'gpt-4.1': {'input': 2.00e-6, 'cached_input': 0.50e-6, 'cache_write': None, 'output': 8.00e-6},
    'gpt-4.1-2025-04-14': {'input': 2.00e-6, 'cached_input': 0.50e-6, 'cache_write': None, 'output': 8.00e-6},
    'gpt-5.4-2026-03-05': {'input': 2.50e-6, 'cached_input': 0.25e-6, 'cache_write': None, 'output': 15.00e-6},
    'gpt-6.1-sol': {'input': 2.00e-6, 'cached_input': 0.10e-6, 'cache_write': 2.50e-6, 'output': 10.00e-6},
}
# Used only when a request carries no output cap (the provider's maximum output for that model).
MAX_OUTPUT = {'gpt-4o-mini-2024-07-18': 16384, 'gpt-4o-mini': 16384, 'gpt-4.1': 32768, 'gpt-4.1-2025-04-14': 32768,
              'gpt-5.4-2026-03-05': 128000, 'gpt-6.1-sol': 128000}
INPUT_MARGIN = 1.05  # The estimate counts the whole JSON body (escapes, schema); 5% more for tokenizer differences.


class PricingUnavailable(BaseException):
    """No verified price for this model: nothing is sent."""


def rates(model):
    name = (model or '').split('/', 1)[-1]
    if name not in PRICES:
        raise PricingUnavailable(f'No verified price for model {model!r}; refusing to send without a cost bound.')
    return PRICES[name]


def count_tokens(text):
    import tiktoken
    return len(tiktoken.get_encoding('o200k_base').encode(text))


def body_fields(body):
    """(model, input token estimate, output cap) from an outgoing JSON body."""
    data = json.loads(body)
    text = body.decode('utf-8') if isinstance(body, (bytes, bytearray)) else str(body)
    model = data.get('model')
    cap = data.get('max_completion_tokens') or data.get('max_tokens') or data.get('max_output_tokens')
    name = (model or '').split('/', 1)[-1]
    return model, int(count_tokens(text) * INPUT_MARGIN) + 64, int(cap or MAX_OUTPUT.get(name, 0))


def reservation(model, input_tokens, output_cap):
    """The most this request can cost: every input token at the higher of input and cache-write rates, the full output
    cap (reasoning tokens are billed as output within it), plus fees."""
    r = rates(model)
    if output_cap <= 0:
        raise PricingUnavailable(f'No output bound for {model!r}.')
    return (input_tokens * max(r['input'], r['cache_write'] or 0) + output_cap * r['output']) * (1 + FEE_RATE)


def settled_cost(model, usage):
    """Cost from provider-reported usage, or None when usage is missing (the reservation is then kept). Without a
    reported cache-write count, a model with a write charge has every uncached input token priced as a write."""
    if not isinstance(usage, dict) or not isinstance(usage.get('prompt_tokens', usage.get('input_tokens')), int):
        return None
    r = rates(model)
    prompt = usage.get('prompt_tokens', usage.get('input_tokens'))
    output = usage.get('completion_tokens', usage.get('output_tokens')) or 0
    details = usage.get('prompt_tokens_details') or usage.get('input_tokens_details') or {}
    cached = details.get('cached_tokens') or 0
    writes = details.get('cache_write_tokens')
    if r['cache_write'] is None:
        writes = 0
    elif writes is None:
        writes = prompt - cached
    plain = max(prompt - cached - writes, 0)
    return (plain * r['input'] + cached * r['cached_input'] + writes * (r['cache_write'] or 0) + output * r['output']) * (1 + FEE_RATE)


def cache_savings(model, usage):
    """What cache reads saved against the standard input rate (reads only; writes are a cost)."""
    details = (usage or {}).get('prompt_tokens_details') or (usage or {}).get('input_tokens_details') or {}
    r = rates(model)
    return (details.get('cached_tokens') or 0) * (r['input'] - r['cached_input'])
