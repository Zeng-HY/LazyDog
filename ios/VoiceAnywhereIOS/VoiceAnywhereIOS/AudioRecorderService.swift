import AVFAudio
import Foundation

protocol AudioRecording: AnyObject {
    var isRecording: Bool { get }
    var elapsedSeconds: TimeInterval { get }
    func requestPermission() async -> Bool
    func start() throws
    func stop() throws -> URL
    func cancel()
}

final class AudioRecorderService: NSObject, AudioRecording {
    private var recorder: AVAudioRecorder?
    private var recordingURL: URL?

    var isRecording: Bool { recorder?.isRecording ?? false }
    var elapsedSeconds: TimeInterval { recorder?.currentTime ?? 0 }

    func requestPermission() async -> Bool {
        await withCheckedContinuation { continuation in
            AVAudioSession.sharedInstance().requestRecordPermission { granted in
                continuation.resume(returning: granted)
            }
        }
    }

    func start() throws {
        cancel()
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.record, mode: .measurement, options: [.duckOthers])
        try session.setActive(true)
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("voiceanywhere-\(UUID().uuidString)")
            .appendingPathExtension("m4a")
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: 44_100,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]
        let recorder = try AVAudioRecorder(url: url, settings: settings)
        recorder.prepareToRecord()
        guard recorder.record() else {
            throw VoiceAnywhereError.recordingFailed("无法开始录音。")
        }
        self.recorder = recorder
        recordingURL = url
    }

    func stop() throws -> URL {
        guard let recorder, let url = recordingURL else {
            throw VoiceAnywhereError.recordingFailed("当前没有可停止的录音。")
        }
        recorder.stop()
        self.recorder = nil
        recordingURL = nil
        try AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        return url
    }

    func cancel() {
        recorder?.stop()
        recorder = nil
        if let recordingURL {
            try? FileManager.default.removeItem(at: recordingURL)
        }
        recordingURL = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}
