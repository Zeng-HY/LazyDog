import SwiftUI
import UIKit

struct ContentView: View {
    @StateObject var viewModel: VoiceSessionViewModel
    @State private var showingShareSheet = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    policyCard
                    Picker("输出语言", selection: $viewModel.outputLanguage) {
                        ForEach(OutputLanguage.allCases) { language in
                            Text(language.title).tag(language)
                        }
                    }
                    .pickerStyle(.segmented)

                    Picker("输入场景", selection: $viewModel.scene) {
                        ForEach(InputScene.allCases) { scene in
                            Text(scene.title).tag(scene)
                        }
                    }
                    .pickerStyle(.segmented)

                    recordingControls
                    statusCard
                    resultCard
                }
                .padding()
            }
            .navigationTitle("VoiceAnywhere")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("API Key") { viewModel.showingKeySheet = true }
                }
            }
            .sheet(isPresented: $viewModel.showingKeySheet) {
                APIKeySheet(viewModel: viewModel)
            }
            .sheet(isPresented: $showingShareSheet) {
                if let result = viewModel.result {
                    ShareSheet(items: [result.text])
                }
            }
        }
    }

    private var policyCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("自动默认策略")
                .font(.headline)
            Text("系统只在有明确依据时处理填充音、改口、标点、分段或分点；不确定时保留原话，不自动扩写、摘要、重排或发送。")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private var recordingControls: some View {
        switch viewModel.state {
        case .recording:
            VStack(spacing: 12) {
                Text("正在录音 \(viewModel.recordingSeconds, format: .number.precision(.fractionLength(1))) 秒")
                    .font(.headline)
                    .foregroundStyle(.red)
                HStack {
                    Button("取消", role: .destructive) { viewModel.cancel() }
                    Spacer()
                    Button("停止并整理") { viewModel.stopAndProcess() }
                        .buttonStyle(.borderedProminent)
                }
            }
        case .transcribing, .composing, .requestingMicrophone:
            HStack {
                ProgressView()
                Text(viewModel.state.title)
                Spacer()
                Button("取消", role: .destructive) { viewModel.cancel() }
            }
        default:
            Button {
                viewModel.startRecording()
            } label: {
                Label("按此开始录音", systemImage: "mic.fill")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(viewModel.state.title)
                .font(.headline)
            if let stopToASR = viewModel.timings.stopToASRMilliseconds {
                Text("停止到识别完成：\(stopToASR) ms")
            }
            if let compose = viewModel.timings.composeMilliseconds {
                Text("自动整理：\(compose) ms")
            }
            if let total = viewModel.timings.stopToResultMilliseconds {
                Text("停止到结果：\(total) ms")
            }
        }
        .font(.subheadline)
        .foregroundStyle(.secondary)
    }

    @ViewBuilder
    private var resultCard: some View {
        if let result = viewModel.result {
            VStack(alignment: .leading, spacing: 14) {
                Text("自动整理结果")
                    .font(.headline)
                Text(result.text.isEmpty ? "（没有可输入的正文）" : result.text)
                    .textSelection(.enabled)
                HStack {
                    Button("复制") { viewModel.copyResult() }
                    Button("系统分享") {
                        viewModel.markShared()
                        showingShareSheet = true
                    }
                }
                if !viewModel.transcript.isEmpty {
                    DisclosureGroup("原转写") {
                        Text(viewModel.transcript).textSelection(.enabled)
                    }
                }
                if !result.attention.isEmpty {
                    DisclosureGroup("需确认的具体疑点") {
                        ForEach(result.attention) { item in
                            VStack(alignment: .leading) {
                                Text(item.span).bold()
                                Text(item.issue)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
            }
            .padding()
            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
        }
    }
}

private struct APIKeySheet: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var viewModel: VoiceSessionViewModel
    @State private var key = ""
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("OpenRouter API Key") {
                    SecureField(viewModel.hasAPIKey ? "已保存；留空则不修改" : "粘贴你的 API Key", text: $key)
                    Text("仅用于个人测试，存入本机 Keychain；不会出现在日志、分享内容或诊断记录中。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    if let errorMessage {
                        Text(errorMessage).foregroundStyle(.red)
                    }
                }
                Section {
                    Button("保存") {
                        do {
                            try viewModel.saveAPIKey(key)
                            dismiss()
                        } catch {
                            errorMessage = error.localizedDescription
                        }
                    }
                    .disabled(key.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    if viewModel.hasAPIKey {
                        Button("移除 API Key", role: .destructive) {
                            do {
                                try viewModel.forgetAPIKey()
                                dismiss()
                            } catch {
                                errorMessage = error.localizedDescription
                            }
                        }
                    }
                }
            }
            .navigationTitle("API Key")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("关闭") { dismiss() } } }
        }
    }
}

private struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
