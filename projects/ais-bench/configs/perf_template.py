from mmengine.config import read_base

from ais_bench.benchmark.models import VLLMCustomAPIChat
from ais_bench.benchmark.utils.postprocess.model_postprocessors import extract_non_reasoning_content
from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.datasets import SyntheticDataset, MATHEvaluator, math_postprocess_v2

with read_base():
    from ais_bench.benchmark.configs.summarizers.example import summarizer

# --- synthetic tokenid dataset: exact input length, fixed request count ---
synthetic_config = {
    "Type": "tokenid",
    "RequestCount": __NUM_REQUESTS__,
    "TrustRemoteCode": True,
    "TokenIdConfig": {
        "RequestSize": __INPUT_TOKENS__,
        "PrefixLen": 0,
    },
}

synthetic_datasets = [
    dict(
        abbr="synthetic",
        type=SyntheticDataset,
        config=synthetic_config,
        reader_cfg=dict(input_columns=["question"], output_column="answer"),
        infer_cfg=dict(
            prompt_template=dict(type=PromptTemplate, template="{question}"),
            retriever=dict(type=ZeroRetriever),
            inferencer=dict(type=GenInferencer),
        ),
        eval_cfg=dict(
            evaluator=dict(type=MATHEvaluator, version="v2"),
            pred_postprocessor=dict(type=math_postprocess_v2),
        ),
    )
]
datasets = synthetic_datasets

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
        generation_kwargs=dict(temperature=0.01, ignore_eos=__IGNORE_EOS__),
        pred_postprocessor=dict(type=extract_non_reasoning_content),
    )
]

work_dir = "/tmp/ais_bench_out/"
