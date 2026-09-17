import Foundation
import SwiftUI

@MainActor
final class VoiceSessionViewModel: NSObject, ObservableObject {
    @Published private(set) var state: VoiceSessionState
    @Published private(set) var recordingSeconds: TimeInterval = 0
    @Published private(set) var transcript = ""
    @Published private(set) var result: AutoComposeResponse?
    @Published private(set) var timings = SessionTimings()
    @Published var outputLanguage: OutputLanguage = .preserve
    @Published var scene: InputScene = .neutral
    @Published var showingKeySheet = false

    private let audioRecorder: AudioRecording
    private let client: VoiceNetworking
    private let keychain: APIKeyStoring
    private var activeSession = UUID()
    private var durationTimer: Timer?
    private var timeoutTask: Task<Void, Never>?
    private var processingTask: Task<Void, Never>?
    private var stoppedAt: ContinuousClock.Instant?
    private let clock = ContinuousClock()

    init(
        audioRecorder: AudioRecording = AudioRecorderService(),
        client: VoiceNetworking = OpenRouterClient(),
        keychain: APIKeyStoring = KeychainStore()
    ) {
        self.audioRecorder = audioRecorder
        self.client = client
        self.keychain = keychain
        self.state = (try? keychain.readAPIKey()) == nil ? .needsKey : .idle
        super.init()
    }

    var hasAPIKey: Bool { (try? keychain.readAPIKey()) != nil }

    func saveAPIKey(_ key: String) throws {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { throw VoiceAnywhereError.missingAPIKey }
        try keychain.saveAPIKey(trimmed)
        state = .idle
    }

    func forgetAPIKey() throws {
        try keychain.deleteAPIKey()
        cancel()
        state = .needsKey
    }

    func startRecording() {
        guard hasAPIKey else {
            state = .needsKey
            showingKeySheet = true
            return
        }
        guard case .idle = state else { return }
        state = .requestingMicrophone
        Task { [weak self] in
            guard let self else { return }
            guard await audioRecorder.requestPermission() else {
                state = .failed(VoiceAnywhereError.microphoneDenied.localizedDescription)
                return
            }
            do {
                try audioRecorder.start()
                let id = UUID()
                activeSession = id
                recordingSeconds = 0
                transcript = ""
                result = nil
                timings = SessionTimings(recordingStartedAt: Date())
                state = .recording
                startDurationTimer()
                timeoutTask = Task { [weak self] in
                    try? await Task.sleep(for: .seconds(120))
                    guard !Task.isCancelled else { return }
                    await MainActor.run {
                        self?.stopAndProcess(expectedSession: id)
                    }
                }
            } catch {
                state = .failed(error.localizedDescription)
            }
        }
    }

    func stopAndProcess(expectedSession: UUID? = nil) {
        guard case .recording = state else { return }
        if let expectedSession, expectedSession != activeSession { return }
        durationTimer?.invalidate()
        durationTimer = nil
        timeoutTask?.cancel()
        timeoutTask = nil
        let session = activeSession
        do {
            let audioURL = try audioRecorder.stop()
            guard recordingSeconds >= 0.2 else {
                try? FileManager.default.removeItem(at: audioURL)
                state = .failed(VoiceAnywhereError.noUsableSpeech.localizedDescription)
                return
            }
            guard let key = try keychain.readAPIKey() else {
                try? FileManager.default.removeItem(at: audioURL)
                state = .needsKey
                return
            }
            stoppedAt = clock.now
            timings.recordingStoppedAt = Date()
            state = .transcribing
            processingTask = Task { [weak self] in
                guard let self else { return }
                defer { try? FileManager.default.removeItem(at: audioURL) }
                do {
                    let asrStarted = clock.now
                    let finalTranscript = try await client.transcribe(audioURL: audioURL, apiKey: key)
                    guard activeSession == session, !Task.isCancelled else { return }
                    transcript = finalTranscript
                    timings.stopToASRMilliseconds = elapsedMilliseconds(from: stoppedAt ?? asrStarted, to: clock.now)
                    timings.transcriptionCompletedAt = Date()
                    state = .composing
                    let composeStarted = clock.now
                    let composeResult = try await client.compose(
                        transcript: finalTranscript,
                        outputLanguage: outputLanguage,
                        scene: scene,
                        terms: [],
                        apiKey: key
                    )
                    guard activeSession == session, !Task.isCancelled else { return }
                    result = composeResult
                    timings.composeMilliseconds = elapsedMilliseconds(from: composeStarted, to: clock.now)
                    timings.stopToResultMilliseconds = elapsedMilliseconds(from: stoppedAt ?? composeStarted, to: clock.now)
                    timings.compositionCompletedAt = Date()
                    state = .complete
                } catch is CancellationError {
                    return
                } catch {
                    guard activeSession == session else { return }
                    state = .failed(error.localizedDescription)
                }
            }
        } catch {
            state = .failed(error.localizedDescription)
        }
    }

    func cancel() {
        activeSession = UUID()
        processingTask?.cancel()
        processingTask = nil
        timeoutTask?.cancel()
        timeoutTask = nil
        durationTimer?.invalidate()
        durationTimer = nil
        audioRecorder.cancel()
        recordingSeconds = 0
        if hasAPIKey { state = .idle }
    }

    func copyResult() {
        guard let result else { return }
        UIPasteboard.general.string = result.text
        timings.copiedAt = Date()
    }

    func markShared() {
        timings.sharedAt = Date()
    }

    private func startDurationTimer() {
        durationTimer?.invalidate()
        durationTimer = Timer.scheduledTimer(
            timeInterval: 0.1,
            target: self,
            selector: #selector(updateRecordingSeconds),
            userInfo: nil,
            repeats: true
        )
    }

    @objc private func updateRecordingSeconds() {
        recordingSeconds = audioRecorder.elapsedSeconds
    }

    private func elapsedMilliseconds(from start: ContinuousClock.Instant, to end: ContinuousClock.Instant) -> Int {
        let components = start.duration(to: end).components
        return Int(components.seconds * 1_000) + Int(components.attoseconds / 1_000_000_000_000_000)
    }
}
