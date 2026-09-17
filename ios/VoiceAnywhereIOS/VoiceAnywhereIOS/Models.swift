import Foundation

enum OutputLanguage: String, CaseIterable, Identifiable, Codable {
    case preserve
    case zh
    case en

    var id: String { rawValue }

    var title: String {
        switch self {
        case .preserve: return "保持原语言"
        case .zh: return "中文"
        case .en: return "英文"
        }
    }
}

enum InputScene: String, CaseIterable, Identifiable, Codable {
    case neutral
    case chat
    case email

    var id: String { rawValue }

    var title: String {
        switch self {
        case .neutral: return "通用文本"
        case .chat: return "聊天"
        case .email: return "邮件正文"
        }
    }
}

struct ConfirmedTerm: Codable, Equatable, Identifiable {
    let spoken: String
    let written: String

    var id: String { "\(spoken)->\(written)" }
}

struct AutoSettings: Codable, Equatable {
    let editLevel = "auto"
    let fillerPolicy = "remove_meaningless"
    let outputLanguage: String
    let tone = "preserve"
    let layout = "auto"
    let punctuation = "standard"
    let numberStyle = "normalize_unambiguous"
    let appStyle: String

    enum CodingKeys: String, CodingKey {
        case editLevel = "edit_level"
        case fillerPolicy = "filler_policy"
        case outputLanguage = "output_language"
        case tone
        case layout
        case punctuation
        case numberStyle = "number_style"
        case appStyle = "app_style"
    }
}

struct AutoComposeInput: Codable, Equatable {
    let transcript: String
    let nearbyText: String
    let confirmedTerms: [ConfirmedTerm]
    let settings: AutoSettings

    enum CodingKeys: String, CodingKey {
        case transcript
        case nearbyText = "nearby_text"
        case confirmedTerms = "confirmed_terms"
        case settings
    }
}

struct AttentionItem: Codable, Equatable, Identifiable {
    let span: String
    let issue: String

    var id: String { "\(span)|\(issue)" }
}

struct AutoComposeResponse: Codable, Equatable {
    let text: String
    let attention: [AttentionItem]
}

struct SessionTimings: Equatable {
    var recordingStartedAt: Date?
    var recordingStoppedAt: Date?
    var transcriptionCompletedAt: Date?
    var compositionCompletedAt: Date?
    var copiedAt: Date?
    var sharedAt: Date?
    var stopToASRMilliseconds: Int?
    var composeMilliseconds: Int?
    var stopToResultMilliseconds: Int?
}

enum VoiceSessionState: Equatable {
    case needsKey
    case idle
    case requestingMicrophone
    case recording
    case transcribing
    case composing
    case complete
    case failed(String)

    var title: String {
        switch self {
        case .needsKey: "请先设置 OpenRouter API Key"
        case .idle: "准备就绪"
        case .requestingMicrophone: "正在请求麦克风权限"
        case .recording: "正在录音"
        case .transcribing: "正在识别"
        case .composing: "正在自动整理"
        case .complete: "已完成"
        case .failed(let message): message
        }
    }
}

enum VoiceAnywhereError: LocalizedError, Equatable {
    case missingAPIKey
    case microphoneDenied
    case noUsableSpeech
    case recordingFailed(String)
    case serviceFailed(String)
    case cancelled

    var errorDescription: String? {
        switch self {
        case .missingAPIKey: "请先设置 OpenRouter API Key。"
        case .microphoneDenied: "未获得麦克风权限。请在系统设置中允许 VoiceAnywhere 使用麦克风。"
        case .noUsableSpeech: "没有录到可用语音。"
        case .recordingFailed(let message), .serviceFailed(let message): message
        case .cancelled: "本次已取消。"
        }
    }
}
