from mmengine.config import read_base

from ais_bench.benchmark.models import VLLMCustomAPIChat
from ais_bench.benchmark.utils.postprocess.model_postprocessors import extract_non_reasoning_content

with read_base():
    from ais_bench.benchmark.configs.datasets.__DATASET_MODULE__ import __DATASETS_VAR__

datasets = __DATASETS_VAR__

models = [
    dict(
        attr="service",
        type=VLLMCustomAPIChat,
        abbr="__MODEL__",
        path="/tok",
        model="__MODEL__",
        stream=True,
        request_rate=__REQUEST_RATE__,
        use_timestamp=False,
        retry=2,
        api_key="__API_KEY__",
        url="__URL__",
        enable_ssl=True,
        max_out_len=__OUTPUT_TOKENS__,
        batch_size=__CONCURRENCY__,
        trust_remote_code=True,
        generation_kwargs=dict(temperature=0.01, ignore_eos=True),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    )
]

work_dir = "/tmp/ais_bench_out/"
