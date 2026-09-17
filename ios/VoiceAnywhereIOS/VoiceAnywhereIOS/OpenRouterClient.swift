import Foundation

protocol VoiceNetworking {
    func transcribe(audioURL: URL, apiKey: String) async throws -> String
    func compose(
        transcript: String,
        outputLanguage: OutputLanguage,
        scene: InputScene,
        terms: [ConfirmedTerm],
        apiKey: String
    ) async throws -> AutoComposeResponse
}

enum OpenRouterClientError: LocalizedError {
    case policyUnavailable
    case invalidResponse
    case http(Int, String)

    var errorDescription: String? {
        switch self {
        case .policyUnavailable: "App 内未找到自动整理策略资源。"
        case .invalidResponse: "服务返回的数据无法解析。"
        case .http(let code, let message): "服务请求失败（HTTP \(code)）：\(message)"
        }
    }
}

struct OpenRouterClient: VoiceNetworking {
    private let baseURL = URL(string: "https://openrouter.ai/api/v1")!
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func transcribe(audioURL: URL, apiKey: String) async throws -> String {
        let audioData = try Data(contentsOf: audioURL)
        let boundary = "VoiceAnywhere-\(UUID().uuidString)"
        var request = URLRequest(url: baseURL.appending(path: "audio/transcriptions"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = MultipartBody.make(
            boundary: boundary,
            fields: ["model": "openai/gpt-transcribe"],
            fileName: "voice.m4a",
            mimeType: "audio/mp4",
            data: audioData
        )
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
        let payload = try JSONDecoder().decode(TranscriptionResponse.self, from: data)
        guard !payload.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw VoiceAnywhereError.noUsableSpeech
        }
        return payload.text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func compose(
        transcript: String,
        outputLanguage: OutputLanguage,
        scene: InputScene,
        terms: [ConfirmedTerm],
        apiKey: String
    ) async throws -> AutoComposeResponse {
        guard let policyURL = Bundle.main.url(forResource: "auto_default_policy_v1", withExtension: "txt"),
              let policy = try? String(contentsOf: policyURL, encoding: .utf8) else {
            throw OpenRouterClientError.policyUnavailable
        }
        let input = AutoComposeInput(
            transcript: transcript,
            nearbyText: "",
            confirmedTerms: terms,
            settings: AutoSettings(outputLanguage: outputLanguage.rawValue, appStyle: scene.rawValue)
        )
        let inputData = try JSONEncoder().encode(input)
        let inputJSON = String(decoding: inputData, as: UTF8.self)
        let body = ComposeRequestFactory.makeBody(policy: policy, userInputJSON: inputJSON)
        var request = URLRequest(url: baseURL.appending(path: "chat/completions"))
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
        let completion = try JSONDecoder().decode(ChatCompletionResponse.self, from: data)
        guard let content = completion.choices.first?.message.content,
              let contentData = content.data(using: .utf8) else {
            throw OpenRouterClientError.invalidResponse
        }
        return try JSONDecoder().decode(AutoComposeResponse.self, from: contentData)
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { throw OpenRouterClientError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(APIErrorResponse.self, from: data).error.message)
                ?? String(decoding: data, as: UTF8.self)
            throw OpenRouterClientError.http(http.statusCode, message.isEmpty ? "请检查网络和 API Key。" : message)
        }
    }
}

enum ComposeRequestFactory {
    static func makeBody(policy: String, userInputJSON: String) -> [String: Any] {
        [
            "model": "openai/gpt-5.6-luna",
            "messages": [
                ["role": "system", "content": policy],
                ["role": "user", "content": userInputJSON]
            ],
            "reasoning": ["effort": "low"],
            "max_tokens": 2048,
            "response_format": [
                "type": "json_schema",
                "json_schema": [
                    "name": "voice_compose_auto_v1",
                    "strict": true,
                    "schema": [
                        "type": "object",
                        "properties": [
                            "text": ["type": "string"],
                            "attention": [
                                "type": "array",
                                "maxItems": 2,
                                "items": [
                                    "type": "object",
                                    "properties": [
                                        "span": ["type": "string"],
                                        "issue": ["type": "string"]
                                    ],
                                    "required": ["span", "issue"],
                                    "additionalProperties": false
                                ]
                            ]
                        ],
                        "required": ["text", "attention"],
                        "additionalProperties": false
                    ]
                ]
            ],
            "provider": [
                "order": ["OpenAI"],
                "allow_fallbacks": false,
                "require_parameters": true
            ]
        ]
    }
}

private struct TranscriptionResponse: Decodable { let text: String }

private struct ChatCompletionResponse: Decodable {
    struct Choice: Decodable {
        struct Message: Decodable { let content: String? }
        let message: Message
    }
    let choices: [Choice]
}

private struct APIErrorResponse: Decodable {
    struct APIError: Decodable { let message: String }
    let error: APIError
}

private enum MultipartBody {
    static func make(boundary: String, fields: [String: String], fileName: String, mimeType: String, data: Data) -> Data {
        var body = Data()
        for (name, value) in fields {
            body.append("--\(boundary)\r\n")
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            body.append("\(value)\r\n")
        }
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n")
        body.append("Content-Type: \(mimeType)\r\n\r\n")
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n")
        return body
    }
}

private extension Data {
    mutating func append(_ string: String) {
        append(string.data(using: .utf8)!)
    }
}
