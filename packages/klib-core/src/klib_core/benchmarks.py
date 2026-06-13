from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .engine import ForgeEngine
from .errors import LibraryNotFoundError
from .library import LibraryManager
from .manifest import save_manifest

BIOLOGY_BENCHMARK_ID = "vesperomyces-biology-benchmark"
BIOLOGY_BENCHMARK_MODEL = "meta/llama-3.3-70b-instruct"
LITERATURE_BIOLOGY_BENCHMARK_ID = "primary-literature-biology-benchmark"

BIOLOGY_SOURCE = """# Vesperomyces marina reference dossier

Vesperomyces marina is a fictional marine microorganism created solely for
controlled K-LIB evaluation. The facts in this dossier do not describe a real
organism.

## Nitrogen metabolism

The enzyme Luma reductase, encoded by the gene LurA, converts nitrite to
ammonium only when the surrounding pH is below 6.4. The regulatory protein Brx7
represses LurA expression when dissolved oxygen rises above 3.2 mg/L.

## Culture conditions

The reference culture uses a salinity of 28 ppt and a temperature of 17 C.
Healthy cultures emit amber fluorescence at 590 nm during stationary phase.

## Contamination check

Growth at 37 C combined with the absence of amber fluorescence at 590 nm is the
benchmark's contamination signature. Either observation alone is insufficient.
"""

BIOLOGY_EVALS = (
    {
        "id": "biology-nitrogen-001",
        "name": "Identify the fictional nitrite reduction mechanism",
        "task": "biological_fact_check",
        "input": (
            "For Vesperomyces marina, name the gene encoding the enzyme that converts "
            "nitrite to ammonium and state the required pH threshold. Cite the source."
        ),
        "checks": {
            "must_include": ["LurA", "6.4"],
            "citation_required": True,
        },
    },
    {
        "id": "biology-regulation-002",
        "name": "Identify the fictional oxygen-dependent regulator",
        "task": "biological_fact_check",
        "input": (
            "What protein represses LurA in Vesperomyces marina, and above what "
            "dissolved-oxygen value does repression occur? Cite the source."
        ),
        "checks": {
            "must_include": ["Brx7", "3.2"],
            "citation_required": True,
        },
    },
    {
        "id": "biology-culture-003",
        "name": "Recover the fictional reference culture conditions",
        "task": "biological_fact_check",
        "input": (
            "State the reference salinity and temperature for Vesperomyces marina. "
            "Cite the source."
        ),
        "checks": {
            "must_include": ["28", "17"],
            "citation_required": True,
        },
    },
    {
        "id": "biology-contamination-004",
        "name": "Recover the two-part fictional contamination signature",
        "task": "biological_fact_check",
        "input": (
            "Which two observations together indicate contamination in the "
            "Vesperomyces marina benchmark? Cite the source."
        ),
        "checks": {
            "must_include": ["37", "590"],
            "citation_required": True,
        },
    },
)

LITERATURE_BIOLOGY_SOURCES = (
    (
        "cayar-ompx-temperature-regulation.md",
        """# Two temperature-responsive RNAs act in concert

Primary study: David A. Guanzon et al., "Two temperature-responsive RNAs act in
concert: the small RNA CyaR and the mRNA ompX." Nucleic Acids Research (2025).
DOI: 10.1093/nar/gkaf041. PMCID: PMC11795201.
Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC11795201/

## Curated evidence

In Yersinia pseudotuberculosis, the small RNA CyaR and the ompX messenger RNA
form a pair of temperature-responsive RNAs. At 25 C, CyaR mainly adopts a
conformation that occludes its seed region. At 37 C, the seed region becomes
liberated. The ompX transcript has RNA-thermometer-like properties that make
CyaR base pairing easier at the higher temperature. The interaction blocks
ribosome binding to ompX and accelerates degradation of the ompX transcript.
Together with increased OmpX protein turnover, these effects lower OmpX levels
at 37 C compared with 25 C.
""",
    ),
    (
        "upec-temperature-virulence.md",
        """# Human body temperature cues virulence expression in UPEC

Primary study: Carolyn A. Dehner et al., "Human body temperature cues widespread
changes in virulence gene expression in uropathogenic Escherichia coli."
Infection and Immunity (2026). DOI: 10.1128/iai.00422-25. PMCID: PMC12890032.
Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC12890032/

## Curated evidence

The researchers studied uropathogenic Escherichia coli strain CFT073. Cells
were initially grown at 23 C and then shifted to 37 C for 4 hours to mimic the
early period of host entry. At a 1% false discovery rate and a threshold of at
least twofold change, messenger RNA expression changed for 9% of the genome.
The proteome showed a similar overall impact. Temperature regulation included
operons associated with fimbrial adhesion, biofilm formation, immune evasion,
and defense against competing bacteria and phages.
""",
    ),
    (
        "ocean-depth-small-proteins.md",
        """# Prokaryotic small proteins across the full ocean-depth gradient

Primary study: Qing-Mei Li, Li-Sheng He, and Yong Wang, "Small proteins from
prokaryotes in the marine water column at full ocean depth." iScience (2026).
DOI: 10.1016/j.isci.2025.114585. PMCID: PMC12856327.
Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC12856327/

## Curated evidence

The study analyzed 71 western Pacific metagenomes and predicted 433,311 complete
short open reading frames encoding proteins no longer than 50 amino acids.
Clustering produced 193,281 small-protein clusters. Filtering identified 75,581
prevalent clusters, including 4,307 high-confidence clusters called RfSPs.
Among the RfSPs, 87.09% lacked non-marine homologs and about 70% contained
unknown domains. Most RfSPs, 65.57%, were phylum-specific.
""",
    ),
    (
        "preferential-lipid-solvation.md",
        """# Preferential lipid solvation regulates CLC-ec1 dimerization

Primary study: Nathan Bernhardt et al., "Molecular basis for the regulation of
membrane proteins through preferential lipid solvation." Nature Chemical
Biology (2025). DOI: 10.1038/s41589-025-02032-w. PMCID: PMC12879294.
Source: https://www.nature.com/articles/s41589-025-02032-w

## Curated evidence

The study combined single-molecule experiments and computational analyses to
examine dimerization of the CLC-ec1 chloride/proton antiporter. The observed
lipid effect did not require long-lived binding at specific protein sites.
Instead, preferential lipid solvation altered the relative thermodynamic
stability of monomers and dimers. The paper uses DL for short-chain dilauroyl
lipids, including DLPC in the simulations. Increasing DL lipids by 20% changed
the net solvation free-energy difference by about 2.5 kcal/mol. That stability
change corresponds to about a 70-fold change in the dissociation constant.
""",
    ),
    (
        "pinnacle-contextual-protein-model.md",
        """# PINNACLE contextual protein representations

Primary study: Michelle M. Li et al., "Contextual AI models for single-cell
protein biology." Nature Methods 21, 1546-1557 (2024).
DOI: 10.1038/s41592-024-02341-3.
Source: https://www.nature.com/articles/s41592-024-02341-3

## Curated evidence

PINNACLE is a geometric deep-learning approach that integrates single-cell
transcriptomics, protein interaction networks, cell-type interactions, and a
tissue hierarchy. It produced 394,760 contextualized protein representations
from 156 cell-type contexts across 24 sampled tissues. After adding ancestor
nodes from the tissue hierarchy, the model represented 62 tissue nodes. Unlike
context-free methods that produce one representation per protein, PINNACLE can
produce a distinct representation for each cell type in which a protein is
activated.
""",
    ),
)

LITERATURE_BIOLOGY_EVALS = (
    {
        "id": "literature-rna-thermometer-001",
        "name": "Recover the temperature-responsive ompX regulation mechanism",
        "task": "primary_literature_fact_check",
        "input": (
            "In the 2025 Guanzon et al. study of Yersinia pseudotuberculosis, "
            "which small RNA regulates ompX at host temperature, at what "
            "temperature is its seed region liberated, and what happens to "
            "ribosome binding? Cite the supplied primary-study evidence."
        ),
        "checks": {
            "must_include": ["CyaR", "ompX", "37", "ribosome"],
            "citation_required": True,
        },
    },
    {
        "id": "literature-upec-temperature-002",
        "name": "Recover the UPEC temperature-shift design and transcriptome result",
        "task": "primary_literature_fact_check",
        "input": (
            "For the Dehner et al. UPEC temperature study, identify the strain, "
            "the starting and shifted temperatures, the shift duration, and the "
            "percentage of the genome with changed mRNA expression. Cite the "
            "supplied primary-study evidence."
        ),
        "checks": {
            "must_include": ["CFT073", "23", "37"],
            "must_include_any": [["4 h", "4 hours"], ["9%", "9 percent"]],
            "citation_required": True,
        },
    },
    {
        "id": "literature-ocean-small-proteins-003",
        "name": "Recover the ocean-depth small-protein counts",
        "task": "primary_literature_fact_check",
        "input": (
            "In the full-ocean-depth prokaryotic small-protein study, how many "
            "short open reading frames were predicted, how many high-confidence "
            "RfSP clusters remained, and what percentage lacked non-marine "
            "homologs? Cite the supplied primary-study evidence."
        ),
        "checks": {
            "must_include_any": [
                ["433,311", "433311"],
                ["4,307", "4307"],
                ["87.09%", "87.09 percent"],
            ],
            "citation_required": True,
        },
    },
    {
        "id": "literature-lipid-solvation-004",
        "name": "Recover the quantitative CLC-ec1 lipid-solvation result",
        "task": "primary_literature_fact_check",
        "input": (
            "In the CLC-ec1 preferential-lipid-solvation study, what lipid "
            "composition change produced what free-energy change, and about how "
            "much did the dissociation constant change? Cite the supplied "
            "primary-study evidence."
        ),
        "checks": {
            "must_include": ["20%", "2.5", "70"],
            "must_include_any": [["kcal/mol", "kcal mol"], ["fold", "times"]],
            "citation_required": True,
        },
    },
    {
        "id": "literature-pinnacle-005",
        "name": "Recover PINNACLE representation and context counts",
        "task": "primary_literature_fact_check",
        "input": (
            "According to the PINNACLE primary study, how many contextualized "
            "protein representations were generated, from how many cell-type "
            "contexts and sampled tissues? Also state the number of tissue nodes "
            "after adding the hierarchy. Cite the supplied primary-study evidence."
        ),
        "checks": {
            "must_include_any": [
                ["394,760", "394760"],
                ["156"],
                ["24"],
                ["62"],
            ],
            "citation_required": True,
        },
    },
)


def install_biology_benchmark(
    manager: LibraryManager,
    *,
    model: str = BIOLOGY_BENCHMARK_MODEL,
) -> Path:
    try:
        manifest, library_path = manager.get(BIOLOGY_BENCHMARK_ID)
    except LibraryNotFoundError:
        manifest = manager.create(
            "Vesperomyces Biology Benchmark",
            library_id=BIOLOGY_BENCHMARK_ID,
            description=(
                "Synthetic biology facts for controlled baseline-versus-K-LIB evaluation."
            ),
            domain="biology/synthetic-benchmark",
        )
        _, library_path = manager.get(BIOLOGY_BENCHMARK_ID)
        manifest.languages = ["en"]
        manifest.default_mode = "biological_fact_check"
        manifest.supported_tasks = ["biological_fact_check"]
        manifest.retrieval_policy.top_k = 4
        manifest.model_policy.default_provider = "nvidia"
        manifest.model_policy.default_model = model
        manifest.model_policy.allow_online_models = True
        save_manifest(library_path, manifest)
        manager.register(library_path)

        manager.add_rule(
            BIOLOGY_BENCHMARK_ID,
            "Use only facts supported by the retrieved Vesperomyces reference dossier.",
            title="Ground answers in the benchmark",
            priority=1,
        )
        manager.add_rule(
            BIOLOGY_BENCHMARK_ID,
            "State when the retrieved source does not contain the requested fact.",
            title="Do not fill evidence gaps",
            priority=2,
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "vesperomyces-reference.md"
            source_path.write_text(BIOLOGY_SOURCE, encoding="utf-8")
            manager.add_sources(BIOLOGY_BENCHMARK_ID, source_path)

        for eval_data in BIOLOGY_EVALS:
            target = library_path / "evals" / f"{eval_data['id']}.json"
            target.write_text(
                json.dumps(eval_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    ForgeEngine(manager).compile(BIOLOGY_BENCHMARK_ID)
    return library_path


def install_literature_biology_benchmark(
    manager: LibraryManager,
    *,
    model: str = BIOLOGY_BENCHMARK_MODEL,
) -> Path:
    try:
        manifest, library_path = manager.get(LITERATURE_BIOLOGY_BENCHMARK_ID)
    except LibraryNotFoundError:
        manifest = manager.create(
            "Primary Literature Biology Benchmark",
            library_id=LITERATURE_BIOLOGY_BENCHMARK_ID,
            description=(
                "Held-out questions backed by curated evidence from primary biology studies."
            ),
            domain="biology/primary-literature",
        )
        _, library_path = manager.get(LITERATURE_BIOLOGY_BENCHMARK_ID)
        manifest.languages = ["en"]
        manifest.default_mode = "primary_literature_fact_check"
        manifest.supported_tasks = ["primary_literature_fact_check"]
        manifest.retrieval_policy.top_k = 3
        manifest.model_policy.default_provider = "nvidia"
        manifest.model_policy.default_model = model
        manifest.model_policy.allow_online_models = True
        save_manifest(library_path, manifest)
        manager.register(library_path)

        manager.add_rule(
            LITERATURE_BIOLOGY_BENCHMARK_ID,
            "Answer only from the retrieved primary-study evidence.",
            title="Use supplied study evidence",
            priority=1,
        )
        manager.add_rule(
            LITERATURE_BIOLOGY_BENCHMARK_ID,
            "Preserve exact organism, strain, molecule, and quantitative identifiers.",
            title="Preserve study-specific details",
            priority=2,
        )
        manager.add_rule(
            LITERATURE_BIOLOGY_BENCHMARK_ID,
            "Do not generalize a paper-specific result beyond the reported study.",
            title="Avoid unsupported generalization",
            priority=3,
        )

        with tempfile.TemporaryDirectory() as temporary_dir:
            source_dir = Path(temporary_dir)
            for filename, content in LITERATURE_BIOLOGY_SOURCES:
                (source_dir / filename).write_text(content, encoding="utf-8")
            manager.add_sources(LITERATURE_BIOLOGY_BENCHMARK_ID, source_dir)

    source_content = dict(LITERATURE_BIOLOGY_SOURCES)
    existing_sources = manager.sources(LITERATURE_BIOLOGY_BENCHMARK_ID)
    existing_titles = {source["title"] for source in existing_sources}
    for source in existing_sources:
        content = source_content.get(source["title"])
        if content is not None:
            (library_path / source["path"]).write_text(content, encoding="utf-8")
    missing_titles = source_content.keys() - existing_titles
    if missing_titles:
        with tempfile.TemporaryDirectory() as temporary_dir:
            source_dir = Path(temporary_dir)
            for filename in missing_titles:
                (source_dir / filename).write_text(source_content[filename], encoding="utf-8")
            manager.add_sources(LITERATURE_BIOLOGY_BENCHMARK_ID, source_dir)

    manifest.model_policy.default_model = model
    save_manifest(library_path, manifest)
    for eval_data in LITERATURE_BIOLOGY_EVALS:
        target = library_path / "evals" / f"{eval_data['id']}.json"
        target.write_text(
            json.dumps(eval_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    ForgeEngine(manager).compile(LITERATURE_BIOLOGY_BENCHMARK_ID)
    return library_path
