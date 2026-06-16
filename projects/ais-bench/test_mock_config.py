from mmengine.config import read_base

from ais_bench.benchmark.models import VLLMCustomAPIChat
from ais_bench.benchmark.utils.postprocess.model_postprocessors import extract_non_reasoning_content

with read_base():
    from ais_bench.benchmark.configs.summarizers.example import summarizer
    from ais_bench.benchmark.configs.datasets.synthetic.synthetic_gen_string import (
        synthetic_datasets,
    )

datasets = synthetic_datasets

models = [
    dict(
        attr="service",
        type=VLLMCustomAPIChat,
        abbr="mock-llm",
        path="/tmp",
        model="mock-model",
        stream=False,
        request_rate=0,
        use_timestamp=False,
        retry=2,
        api_key="",
        host_ip="localhost",
        host_port=8000,
        url="",
        max_out_len=64,
        batch_size=1,
        trust_remote_code=False,
        generation_kwargs=dict(temperature=0.01, ignore_eos=False),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    )
]

work_dir = "/tmp/ais_bench_out/"
