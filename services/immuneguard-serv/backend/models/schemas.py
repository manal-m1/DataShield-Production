from typing import List, Optional
from pydantic import BaseModel, Field


class ColumnMapping(BaseModel):
    """Describes the role(s) assigned to a single column by the user."""
    name: str
    roles: Optional[List[str]] = None
    role: Optional[str] = None
    type: str = Field(default="string", description="Data type: string, int, float")
    description: str = Field(default="")

    def get_roles(self) -> List[str]:
        """Return the effective list of roles, supporting both formats."""
        if self.roles is not None:
            return self.roles
        if self.role is not None:
            return [self.role]
        return []


class AnalysisProfileCreateRequest(BaseModel):
    """Request body for creating an analysis profile from frontend column mappings."""
    dataset_name: str
    description: str = ""
    columns: List[ColumnMapping]
    secteur: Optional[str] = "rh"
    public_sample_frac: float = Field(default=0.15, ge=0.01, le=0.5)
    imbalance_columns: Optional[List[str]] = None
    correlation_columns: Optional[List[str]] = None
    id_column: Optional[str] = None
    sensitive_health_columns: Optional[List[str]] = None


class ScoreRequest(BaseModel):
    """Request body for computing Score A against a dataset already in the platform."""
    dataset_id: str
    profile_name: str


class SignalScanColumnResult(BaseModel):
    raw_column: str
    normalized: str
    match_method: str
    ref_entry: Optional[str] = None
    signal: Optional[str] = None
    mit_domain: str = ""
    legal_source: str = ""
    p: float = 0.0
    xai_template_fr: str = ""
    action_corrective: str = ""
    severity_columns: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    human_validated: bool
    comment: str = ""


class SignalScanMetrics(BaseModel):
    exact: int = 0
    alias: int = 0
    fuzzy: int = 0
    profiling: int = 0
    none: int = 0
    total_columns: int = 0


class SignalScanResponse(BaseModel):
    columns: List[SignalScanColumnResult]
    metrics: SignalScanMetrics

class AnalysisProfileSummary(BaseModel):
    quasi_identifiers: List[str]
    pii_columns: List[str]
    sensitive_attribute: Optional[str] = None
    id_column: Optional[str] = None
    sensitive_health_columns: List[str]


class AnalysisProfileProposalResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    description: str
    secteur: str
    public_sample_frac: float
    columns: List[ColumnMapping]
    imbalance_columns: List[str]
    correlation_columns: List[str]
    id_column: Optional[str] = None
    sensitive_health_columns: List[str]
    scan_result: SignalScanResponse
    derived_summary: AnalysisProfileSummary
