from __future__ import annotations

import pytest

from workers.acquisition.linkedin_qualification import (
    GENUINE_LABEL,
    LinkedInPostSignal,
    OpportunityDisposition,
    classify_linkedin_opportunity,
)


def classify(text: str, **kwargs: str):
    return classify_linkedin_opportunity(LinkedInPostSignal(text=text, **kwargs))


def test_ai_video_animation_social_request_is_genuine() -> None:
    result = classify(
        "Looking for a Digital Agency with expertise in AI-powered videos, animations "
        "and engaging social media content creation",
        original_author="Saad Rasheed",
        interaction_actor="Nidhal Shaikh",
    )
    assert result.disposition is OpportunityDisposition.NEEDS_RESEARCH
    assert result.status_label == GENUINE_LABEL
    assert set(result.matched_services) == {
        "digital_marketing",
        "social_media",
        "content_production",
        "animation",
        "ai_creative",
    }
    assert result.original_author == "Saad Rasheed"
    assert result.interaction_actor == "Nidhal Shaikh"


@pytest.mark.parametrize(
    ("text", "service"),
    [
        ("We are looking for a digital marketing agency for our launch.", "digital_marketing"),
        ("Seeking a social media management partner for three brands.", "social_media"),
        ("Need a vendor for content production and branded content.", "content_production"),
        ("Looking for an animation studio for a 3D campaign film.", "animation"),
        ("We require a video production company for corporate films.", "video_production"),
        ("Searching for an AI creative agency for generative AI content.", "ai_creative"),
    ],
)
def test_direct_agency_service_requests_are_genuine(text: str, service: str) -> None:
    result = classify(text)
    assert result.is_genuine_opportunity is True
    assert result.disposition is OpportunityDisposition.NEEDS_RESEARCH
    assert service in result.matched_services


def test_rfp_for_social_and_content_is_genuine() -> None:
    result = classify("RFP: social media management and content creation services")
    assert result.is_genuine_opportunity is True
    assert result.matched_services == ("social_media", "content_production")


def test_eoi_from_digital_agencies_is_genuine() -> None:
    result = classify("EOI invited from digital agencies for digital marketing and video production")
    assert result.is_genuine_opportunity is True
    assert "digital_marketing" in result.matched_services
    assert "video_production" in result.matched_services


def test_recommendation_request_is_genuine() -> None:
    result = classify("Can anyone recommend an agency for social media and content production?")
    assert result.is_genuine_opportunity is True


def test_hiring_an_agency_is_not_misread_as_job_vacancy() -> None:
    result = classify("We are hiring an agency for video production and animations.")
    assert result.is_genuine_opportunity is True
    assert result.is_job_vacancy is False


def test_service_request_without_agency_word_can_still_be_genuine() -> None:
    result = classify("Need AI-powered videos and animations for a product launch.")
    assert result.is_genuine_opportunity is True
    assert set(result.matched_services) == {"animation", "ai_creative"}


def test_social_media_manager_job_is_not_agency_opportunity() -> None:
    result = classify("We are hiring a full-time social media manager. Send your CV.")
    assert result.disposition is OpportunityDisposition.INDIVIDUAL_HIRING
    assert result.is_genuine_opportunity is False
    assert result.is_job_vacancy is True


def test_video_editor_job_is_not_agency_opportunity() -> None:
    result = classify("Job opening for a video editor at our agency. Apply now.")
    assert result.disposition is OpportunityDisposition.INDIVIDUAL_HIRING


def test_animation_internship_is_not_agency_opportunity() -> None:
    result = classify("Animation internship available. Join our team.")
    assert result.disposition is OpportunityDisposition.INDIVIDUAL_HIRING


def test_generic_marketing_discussion_is_not_opportunity() -> None:
    result = classify("Five digital marketing trends every founder should know.")
    assert result.disposition is OpportunityDisposition.NOT_OPPORTUNITY
    assert "no_buyer_intent" in result.reason_codes


def test_agency_self_promotion_is_not_opportunity() -> None:
    result = classify("We offer social media management and video production. Contact us.")
    assert result.disposition is OpportunityDisposition.NOT_OPPORTUNITY
    assert "seller_self_promotion" in result.reason_codes


def test_award_announcement_is_not_opportunity() -> None:
    result = classify("Our digital marketing agency won an award for branded content.")
    assert result.disposition is OpportunityDisposition.NOT_OPPORTUNITY


def test_empty_text_is_not_opportunity() -> None:
    result = classify("")
    assert result.disposition is OpportunityDisposition.NOT_OPPORTUNITY
    assert result.matched_services == ()


def test_wrapper_identity_is_preserved_without_replacing_original_author() -> None:
    result = classify(
        "Looking for a social media agency.",
        original_author="Original Buyer",
        interaction_actor="Commenter Wrapper",
        canonical_post_url="https://www.linkedin.com/feed/update/urn:li:activity:123",
        source_url="https://www.linkedin.com/posts/wrapper-share",
    )
    assert result.original_author == "Original Buyer"
    assert result.interaction_actor == "Commenter Wrapper"
    assert result.canonical_post_url.endswith("123")
    assert result.source_url.endswith("wrapper-share")


def test_all_results_use_local_only_queue() -> None:
    assert classify("Looking for a digital marketing agency").queue == "local_only"
    assert classify("Digital marketing tips").queue == "local_only"


def test_default_owner_is_waseem() -> None:
    assert classify("Need a video production company").owner == "Waseem"


def test_owner_can_be_overridden_explicitly() -> None:
    result = classify_linkedin_opportunity(
        LinkedInPostSignal(text="Need a content production agency"), owner="Subaina"
    )
    assert result.owner == "Subaina"


def test_service_matches_are_unique_and_stably_ordered() -> None:
    result = classify(
        "Looking for social media, social media management, content creation and content production"
    )
    assert result.matched_services == ("social_media", "content_production")


def test_supported_service_reason_is_recorded() -> None:
    result = classify("Seeking a video production studio")
    assert "supported_agency_service" in result.reason_codes
    assert "buyer_intent" in result.reason_codes
    assert "agency_or_vendor_requested" in result.reason_codes


def test_job_reason_is_recorded() -> None:
    result = classify("We are hiring a full-time content writer. Send your resume.")
    assert "individual_job_vacancy" in result.reason_codes


def test_no_supported_service_is_recorded() -> None:
    result = classify("Looking for an accounting firm")
    assert result.disposition is OpportunityDisposition.NOT_OPPORTUNITY
    assert "no_supported_service" in result.reason_codes


def test_status_label_remains_win_potential_unverified() -> None:
    result = classify("Need an agency for AI video content")
    assert result.status_label == "Genuine opportunity — win potential unverified"


def test_no_external_action_is_exposed_by_decision_model() -> None:
    result = classify("Looking for a social media agency")
    assert not hasattr(result, "send_message")
    assert not hasattr(result, "publish")
    assert not hasattr(result, "deploy")
