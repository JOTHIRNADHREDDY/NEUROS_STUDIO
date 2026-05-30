import { NextResponse } from 'next/server';

type ChatRequest = {
  prompt?: string;
  context?: string;
};

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as ChatRequest;
    const prompt = body.prompt?.trim();

    if (!prompt) {
      return NextResponse.json({ error: 'prompt is required' }, { status: 400 });
    }

    const apiKey = process.env.NVIDIA_API_KEY;
    const baseUrl = process.env.NVIDIA_BASE_URL ?? 'https://integrate.api.nvidia.com/v1';
    const model = process.env.NVIDIA_MODEL ?? 'deepseek-ai/deepseek-v4-pro';

    if (!apiKey) {
      return NextResponse.json(
        { error: 'Missing NVIDIA_API_KEY in environment' },
        { status: 500 }
      );
    }

    const systemMessage = [
      'You are the AI co-pilot for a robotics IDE.',
      'Be concise, practical, and grounded in the provided code context.',
      'If the user asks for code changes, propose focused edits and mention risks briefly.',
    ].join(' ');

    const userContent = body.context
      ? `Context:\n${body.context}\n\nUser request:\n${prompt}`
      : prompt;

    const response = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: systemMessage },
          { role: 'user', content: userContent },
        ],
        temperature: 1,
        top_p: 0.95,
        max_tokens: 16384,
        stream: false,
        extra_body: {
          chat_template_kwargs: {
            thinking: false,
          },
        },
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: 'Upstream model request failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    const reply = data?.choices?.[0]?.message?.content ?? '';

    return NextResponse.json({ reply });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown AI request error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}