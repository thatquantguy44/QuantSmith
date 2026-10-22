"""The governed bridge: the only SFMeridian package that may import ``quantsmith``.

Spec ``0115`` REQ-012 (realizing ``0113`` NFR-003 and REQ-025). Everything
here degrades to plain JSON reading when the QuantSmith SDK is not installed,
so the plugin core stays standard-library only.
"""
