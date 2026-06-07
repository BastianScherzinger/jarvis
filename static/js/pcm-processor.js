/**
 * AudioWorklet Processor — läuft in separatem Audio-Thread
 * Empfängt Float32-PCM vom Mikrofon, sendet Int16-Blöcke an Hauptthread.
 */
class PCMProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const channel = inputs[0]?.[0];
        if (!channel) return true;

        const int16 = new Int16Array(channel.length);
        for (let i = 0; i < channel.length; i++) {
            // Clamp + scale Float32 (-1..1) → Int16 (-32768..32767)
            const s = Math.max(-1, Math.min(1, channel[i]));
            int16[i] = s < 0 ? s * 32768 : s * 32767;
        }
        // Transferable object — zero-copy an den Hauptthread
        this.port.postMessage(int16.buffer, [int16.buffer]);
        return true;
    }
}
registerProcessor("pcm-processor", PCMProcessor);
