class MediaPolicyFailure(RuntimeError):
    pass


class VoicePolicyFailure(MediaPolicyFailure):
    pass


class MediaAssetPolicyFailure(MediaPolicyFailure):
    pass


class NarrationAuditFailure(MediaPolicyFailure):
    pass
