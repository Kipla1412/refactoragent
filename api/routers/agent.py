from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import json
from typing import Optional
import traceback
from api.auth import require_permission
from agent.events import AgentType
from customagents.factory import AgentFactory

router = APIRouter(prefix="/agent")

class ConversationRequest(BaseModel):
    conversation: List[str] = Field(
        ...,
        description="Doctor patient conversation transcript"
    )
    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation": [
                    "Doctor: What brings you in today?",
                    "Patient: I have had a fever for 3 days.",
                    "Doctor: Any cough or breathing difficulty?"
                ]
            }
        }
    }


class ErrorResponse(BaseModel):
    error: str
    details: str | None = None

class SOAPSubjective(BaseModel):
    chief_complaint: str | None = None
    history_of_present_illness: str | None = None
    review_of_systems: List[Any] = Field(default_factory=list)
    past_medical_history: List[Any] = Field(default_factory=list)
    past_surgical_history: List[Any] = Field(default_factory=list)
    family_history: List[Any] = Field(default_factory=list)
    social_history: List[Any] = Field(default_factory=list)
    allergies: Dict[str, Any] = Field(default_factory=dict)
    current_medications: List[Any] = Field(default_factory=list)
    relevant_history: List[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SOAPObjective(BaseModel):
    vital_signs: List[Any] = Field(default_factory=list)
    physical_examination: List[Any] = Field(default_factory=list)
    investigation_results: List[Any] = Field(default_factory=list)
    other_observations: List[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SOAPAssessment(BaseModel):
    primary_diagnosis: Any = None
    secondary_diagnoses: List[Any] = Field(default_factory=list)
    active_problems: List[Any] = Field(default_factory=list)
    differential_diagnoses: List[Any] = Field(default_factory=list)
    clinical_reasoning: str | None = None
    uncertainties: List[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SOAPPlan(BaseModel):
    medications: List[Any] = Field(default_factory=list)
    investigations: List[Any] = Field(default_factory=list)
    procedures: List[Any] = Field(default_factory=list)
    referrals: List[Any] = Field(default_factory=list)
    non_pharmacological_management: List[Any] = Field(default_factory=list)
    counselling: List[Any] = Field(default_factory=list)
    follow_up: List[Any] = Field(default_factory=list)
    safety_netting: List[Any] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class SOAPNote(BaseModel):
    subjective: SOAPSubjective = Field(default_factory=SOAPSubjective)
    objective: SOAPObjective = Field(default_factory=SOAPObjective)
    assessment: SOAPAssessment = Field(default_factory=SOAPAssessment)
    plan: SOAPPlan = Field(default_factory=SOAPPlan)

    model_config = {"extra": "allow"}


class SOAPResponse(BaseModel):
    """Mirrors the JSON contract in customagents/reportagent/soapprompt.py.

    Every field has a default and unknown keys are preserved, so partial or
    specialty-extended output still validates instead of failing the response.
    """

    document_type: str | None = None
    document_version: str | None = None
    patient: Dict[str, Any] = Field(default_factory=dict)
    encounter: Dict[str, Any] = Field(default_factory=dict)
    documentation_metadata: Dict[str, Any] = Field(default_factory=dict)
    soap_note: SOAPNote = Field(default_factory=SOAPNote)
    clinical_actions: List[Dict[str, Any]] = Field(default_factory=list)
    review_flags: List[Dict[str, Any]] = Field(default_factory=list)
    completeness: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "example": {
                "document_type": "SOAP_NOTE",
                "document_version": "1.0",
                "patient": {"patient_id": "10008", "display_name": "Jane Doe"},
                "encounter": {"encounter_id": "enc-1", "documentation_status": "DRAFT"},
                "documentation_metadata": {
                    "source_types": ["consultation_transcript"],
                    "requires_clinician_review": True,
                },
                "soap_note": {
                    "subjective": {
                        "chief_complaint": "Fever and cough",
                        "history_of_present_illness": "Fever and cough for 3 days",
                    },
                    "objective": {"vital_signs": [{"name": "Temperature", "value": "101.2", "unit": "F"}]},
                    "assessment": {"primary_diagnosis": {"display": "Upper Respiratory Tract Infection"}},
                    "plan": {"investigations": [{"name": "CBC"}]},
                },
                "clinical_actions": [
                    {"action_id": "a1", "action_type": "Investigation", "description": "CBC"}
                ],
                "review_flags": [],
                "completeness": {"subjective_complete": True, "missing_sections": []},
            }
        },
    }

class AssessmentResponse(BaseModel):
    clinical_overview: str
    differential_diagnosis: List[Dict[str, Any]]
    diagnostic_plan: Dict[str, Any]
    treatment_plan: List[Dict[str, Any]]
    procedures: str
    risk_level: str
    red_flags: List[str]

    model_config = {
        "json_schema_extra": {
            "example": {
                "clinical_overview": "Patient presents with fever, cough, and sore throat for 4 days. Findings suggest mild upper respiratory tract infection.",
                "differential_diagnosis": [
                    {
                        "condition": "Viral Upper Respiratory Tract Infection",
                        "likelihood": "high",
                        "rationale": "Most symptoms are consistent with viral URI."
                    },
                    {
                        "condition": "Bacterial Pharyngitis",
                        "likelihood": "moderate",
                        "rationale": "Fever and sore throat are present."
                    }
                ],
                "diagnostic_plan": {
                    "laboratory_tests": [
                        {
                            "test": "Complete Blood Count",
                            "purpose": "Assess infection severity."
                        }
                    ],
                    "imaging": [
                        {
                            "study": "Chest X-Ray",
                            "purpose": "Rule out pneumonia."
                        }
                    ]
                },
                "treatment_plan": [
                    {
                        "condition": "Upper Respiratory Tract Infection",
                        "recommendation": "Amoxicillin 500 mg",
                        "route": "oral",
                        "duration": "7 days"
                    },
                    {
                        "condition": "Fever",
                        "recommendation": "Paracetamol 650 mg",
                        "route": "oral",
                        "duration": "as needed"
                    }
                ],
                "procedures": "No procedures required",
                "risk_level": "LOW",
                "red_flags": [
                    "Shortness of breath",
                    "Chest pain",
                    "Persistent high fever"
                ]
            }
        }
    }

class ConsultationWorkflowResponse(BaseModel):
    soap: Dict[str, Any]
    assessment: Dict[str, Any]
    clinicalExtraction: Dict[str, Any]

    model_config = {
        "json_schema_extra": {
            "example": {
                "soap": {
                    "subjective": "Fever for 3 days",
                    "objective": "Temperature 101°F"
                },
                "assessment": {
                    "diagnosis": "Viral Fever",
                    "plan": ["Paracetamol", "Hydration"]
                },
                "clinicalExtraction": {
                    "symptoms": ["Fever"],
                    "medications": ["Paracetamol"]
                }
            }
        }
    }

class ClinicalExtractionRequest(BaseModel):

    soap: Dict[str, Any] = Field(
        ...,
        description="SOAP note output"
    )

    assessment: Dict[str, Any] | None = Field(
        default=None,
        description="Assessment agent output"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "soap": {
                    "subjective": {
                        "chief_complaint": "Fever and cough",
                        "history_of_present_illness": "Fever and cough for 3 days"
                    },
                    "objective": {
                        "observations": [
                            "Temperature: 101.2 F"
                        ]
                    },
                    "assessment": {
                        "possible_conditions": [
                            "Upper Respiratory Tract Infection"
                        ]
                    },
                    "plan": {
                        "next_steps": [
                            "CBC",
                            "Chest X-Ray"
                        ]
                    },
                    "summary": "Patient has fever and cough."
                },
                "assessment": {
                    "clinical_overview": "Likely URTI",
                    "differential_diagnosis": [
                        {
                            "condition": "Viral URI",
                            "likelihood": "high",
                            "rationale": "Symptoms are consistent"
                        }
                    ],
                    "diagnostic_plan": {
                        "laboratory_tests": [
                            {
                                "test": "CBC",
                                "purpose": "Evaluate infection"
                            }
                        ]
                    },
                    "treatment_plan": [
                        {
                            "condition": "URI",
                            "recommendation": "Amoxicillin 500 mg",
                            "route": "oral",
                            "duration": "7 days"
                        }
                    ],
                    "risk_level": "LOW"
                }
            }
        }
    }

class ClinicalCondition(BaseModel):
    display: str
    terminologySystem: str


class ClinicalObservation(BaseModel):
    display: str
    terminologySystem: str
    value: str | None = None
    unit: Optional[str] = None


class MedicationRequest(BaseModel):
    display: str
    terminologySystem: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None


class ServiceRequest(BaseModel):
    display: str
    terminologySystem: str


class ClinicalExtractionResponse(BaseModel):

    conditions: list[ClinicalCondition] = Field(default_factory=list)
    observations: list[ClinicalObservation] = Field(default_factory=list)
    medicationRequests: list[MedicationRequest] = Field(default_factory=list)
    serviceRequests: list[ServiceRequest] = Field(default_factory=list)

    model_config = {
        "json_schema_extra": {
            "example": {
                "conditions": [
                    {
                        "display": "Upper Respiratory Tract Infection",
                        "terminologySystem": "SNOMED"
                    }
                ],
                "observations": [
                    {
                        "display": "Temperature",
                        "terminologySystem": "LOINC",
                        "value": "101.2",
                        "unit": "F"
                    }
                ],
                "medicationRequests": [
                    {
                        "display": "Amoxicillin",
                        "terminologySystem": "RXNORM",
                        "dose": "500 mg",
                        "frequency": "Three times daily",
                        "duration": "7 days",
                        "route": "Oral"
                    }
                ],
                "serviceRequests": [
                    {
                        "display": "Complete Blood Count",
                        "terminologySystem": "LOINC"
                    }
                ]
            }
        }
    }

class DoctorAgentResponse(BaseModel):
    questions: List[str]

class GenericAIResponse(BaseModel):
    result: Dict[str, Any]

@router.post(
    "/doctoragent",
    summary="Doctor Assistant - Medical Question Recommendations",
    description="""
Generate intelligent medical question recommendations for doctors based on patient conversation.

This endpoint analyzes the conversation history and provides targeted follow-up questions
that help doctors gather essential patient information for better medical care.

**Features:**
- Medical question recommendations based on symptoms
- Targeted follow-up questions for clinical assessment
- Context-aware conversation analysis

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- conversation: List of conversation messages between doctor and patient

**Output:**
- Structured question recommendations for clinical use
""",
    response_model=DoctorAgentResponse,
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Failed to generate recommendations"
        }
    },
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def recommend_questions_api(request: Request, data: ConversationRequest):

    if not data.conversation:
        return {"questions": [], "status": "empty_input"}
    
    user_id = request.state.user["sub"]
    config = request.app.state.config
    session = await request.app.state.session_manager.get_session(user_id, config)

    agent = AgentFactory.create(AgentType.DOC, config, session)

    try:
        # await agent.session.initialize()

        result = await agent.recommend_questions(data.conversation)

        return result

    except Exception as e:
        return {
            "questions": [], 
            "error": "Failed to generate recommendations",
            "details": str(e)
        }


@router.post(
    "/soap",
    summary="SOAP Report Generation",
    description="""
Generate professional clinical notes in SOAP format from doctor-patient conversation.

This endpoint processes the complete conversation and creates structured clinical documentation
following the SOAP (Subjective, Objective, Assessment, Plan) format used in medical practice.

**Features:**
- Standard SOAP format documentation
- Professional medical note generation
- Conversation-to-clinical-notes conversion

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- conversation: List of conversation messages to be documented

**Output:**
- Structured SOAP report with all medical sections
""",
    response_model=SOAPResponse,
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Failed to generate SOAP report"
        }
    },
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def generate_soap_api(request: Request, data: ConversationRequest):

    if not data.conversation:
        return {"error": "Conversation is empty"}
    
    user_id = request.state.user["sub"]
    config = request.app.state.config
    session = await request.app.state.session_manager.get_session(user_id, config)

    agent = AgentFactory.create(AgentType.SOAP, config, session)

    try:
        # await agent.session.initialize()

        result = await agent.generate(data.conversation)

        return result

    except Exception as e:
        return {
            "error": "Failed to generate SOAP report",
            "details": str(e)
        }


# Assessment Plan
@router.post(
    "/assessment",
    summary="Medical Assessment and Plan Generation",
    description="""
Generate comprehensive medical assessment and treatment plan from patient conversation.

This endpoint analyzes the complete patient consultation and creates detailed clinical
documentation including differential diagnosis, assessment findings, and recommended
treatment plans for healthcare providers.

**Features:**
- Comprehensive medical assessment generation
- Differential diagnosis analysis
- Treatment plan recommendations
- Clinical decision support
- Evidence-based suggestions

**Authentication:**
Requires valid user session with consultagent:chat permission.

**Input:**
- conversation: List of conversation messages between doctor and patient

**Output:**
- Structured assessment with clinical findings
- Recommended treatment options
- Follow-up care suggestions
- Medical documentation in structured format
""",
    response_model=AssessmentResponse,
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Failed to generate assessment"
        }
    },
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)
async def generate_assessment_api(request: Request, data: ConversationRequest):

    if not data.conversation:
        return {"error": "Conversation is empty"}
    
    user_id = request.state.user["sub"]
    config = request.app.state.config
    session = await request.app.state.session_manager.get_session(user_id, config)

    agent = AgentFactory.create(AgentType.ASSESSMENT, config, session)

    try:
        # await agent.session.initialize()

        result = await agent.generate(data.conversation)

        return result

    except Exception as e:
        return {
            "error": "Failed to generate assessment",
            "details": str(e)
        }

@router.post(
    "/consultation-workflow",
    summary="SOAP + Assessment + Clinical Extraction Workflow",
    description="""
Runs the complete clinical workflow:

1. SOAP Generation
2. Assessment & Plan Generation
3. Clinical Concept Extraction

Returns all outputs in a single response.
""",
    response_model=ConsultationWorkflowResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Conversation is empty"
        },
        500: {
            "model": ErrorResponse,
            "description": "Workflow execution failed"
        }
    },
    dependencies=[Depends(require_permission("consultagent", "chat"))]
)

async def consultation_workflow(
    request: Request,
    data: ConversationRequest
):

    if not data.conversation:
        raise HTTPException(
            status_code=400,
            detail="Conversation is empty"
        )

    user_id = request.state.user["sub"]

    config = request.app.state.config

    session = await request.app.state.session_manager.get_session(
        user_id,
        config
    )

    try:
        # SOAP AGENT
        soap_agent = AgentFactory.create(
            AgentType.SOAP,
            config,
            session
        )

        soap_result = await soap_agent.generate(
            data.conversation
        )

        # ASSESSMENT AGENT
        assessment_agent = AgentFactory.create(
            AgentType.ASSESSMENT,
            config,
            session
        )

        assessment_result = await assessment_agent.generate(
            data.conversation
        )

        # CLINICAL EXTRACTION AGENT
        clinical_agent = AgentFactory.create(
            AgentType.CLINICAL_EXTRACTION,
            config,
            session
        )

        clinical_result = await clinical_agent.generate(
            soap_note=soap_result,
            assessment_report=assessment_result
        )

        return {
            "soap": soap_result,
            "assessment": assessment_result,
            "clinicalExtraction": clinical_result
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Consultation workflow failed: {str(e)}"
        )

@router.post(
    "/clinical-extraction",
    summary="Clinical Concept Extraction",
    response_model=ClinicalExtractionResponse,
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Clinical extraction failed"
        }
    },
    dependencies=[
        Depends(
            require_permission(
                "consultagent",
                "chat"
            )
        )
    ]
)

async def generate_clinical_extraction(
    request: Request,
    data: ClinicalExtractionRequest
):

    user_id = request.state.user["sub"]

    config = request.app.state.config

    session = await request.app.state.session_manager.get_session(
        user_id,
        config
    )

    try:

        agent = AgentFactory.create(
            AgentType.CLINICAL_EXTRACTION,
            config,
            session
        )

        result = await agent.generate(
            soap_note=data.soap,
            assessment_report=data.assessment
        )

        print("=" * 100)
        print(json.dumps(result, indent=2))
        print("=" * 100)

        # result["conditions"] = result.get("conditions") or []
        # result["observations"] = result.get("observations") or []
        # result["medicationRequests"] = result.get("medicationRequests") or []
        # result["serviceRequests"] = result.get("serviceRequests") or []

        # return result

        return ClinicalExtractionResponse(
            conditions=result.get("conditions") or [],
            observations=result.get("observations") or [],
            medicationRequests=result.get("medicationRequests") or [],
            serviceRequests=result.get("serviceRequests") or [],
        )
            

    # except Exception as e:

    #     raise HTTPException(
    #         status_code=500,
    #         detail=f"Clinical extraction failed: {str(e)}"
    #     )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )