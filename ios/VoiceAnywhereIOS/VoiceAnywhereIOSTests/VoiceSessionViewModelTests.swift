import XCTest
@testable import VoiceAnywhereIOS

@MainActor
final class VoiceSessionViewModelTests: XCTestCase {
    func testMissingKeyStartsInNeedsKeyState() {
        let viewModel = VoiceSessionViewModel(
            audioRecorder: FakeRecorder(),
            client: FakeClient(),
            keychain: FakeKeychain(key: nil)
        )
        XCTAssertEqual(viewModel.state, .needsKey)
    }

    func testSaveAndForgetKeyUpdatesState() throws {
        let keychain = FakeKeychain(key: nil)
        let viewModel = VoiceSessionViewModel(
            audioRecorder: FakeRecorder(),
            client: FakeClient(),
            keychain: keychain
        )
        try viewModel.saveAPIKey("test-key")
        XCTAssertEqual(viewModel.state, .idle)
        try viewModel.forgetAPIKey()
        XCTAssertEqual(viewModel.state, .needsKey)
    }

    func testKeychainWriteFailureIsPropagated() {
        let viewModel = VoiceSessionViewModel(
            audioRecorder: FakeRecorder(),
            client: FakeClient(),
            keychain: FailingKeychain()
        )
        XCTAssertThrowsError(try viewModel.saveAPIKey("test-key"))
    }

    func testCancelAlwaysCancelsTheCurrentRecorder() {
        let recorder = FakeRecorder()
        let viewModel = VoiceSessionViewModel(
            audioRecorder: recorder,
            client: FakeClient(),
            keychain: FakeKeychain(key: "test-key")
        )
        viewModel.cancel()
        XCTAssertTrue(recorder.cancelled)
        XCTAssertEqual(viewModel.state, .idle)
    }
}

private final class FakeKeychain: APIKeyStoring {
    var key: String?

    init(key: String?) { self.key = key }
    func readAPIKey() throws -> String? { key }
    func saveAPIKey(_ key: String) throws { self.key = key }
    func deleteAPIKey() throws { key = nil }
}

private final class FakeRecorder: AudioRecording {
    var isRecording = false
    var elapsedSeconds: TimeInterval = 0
    var cancelled = false
    func requestPermission() async -> Bool { true }
    func start() throws { isRecording = true }
    func stop() throws -> URL { isRecording = false; return URL(fileURLWithPath: "/tmp/test.m4a") }
    func cancel() { isRecording = false; cancelled = true }
}

private final class FailingKeychain: APIKeyStoring {
    func readAPIKey() throws -> String? { throw KeychainStoreError.unexpectedData }
    func saveAPIKey(_ key: String) throws { throw KeychainStoreError.unexpectedData }
    func deleteAPIKey() throws { throw KeychainStoreError.unexpectedData }
}

private struct FakeClient: VoiceNetworking {
    func transcribe(audioURL: URL, apiKey: String) async throws -> String { "测试" }
    func compose(transcript: String, outputLanguage: OutputLanguage, scene: InputScene, terms: [ConfirmedTerm], apiKey: String) async throws -> AutoComposeResponse {
        AutoComposeResponse(text: transcript, attention: [])
    }
}
