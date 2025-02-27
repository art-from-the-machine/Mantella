(real-time-npcs)=
# Real-Time NPCs
By default, Mantella is configured to provide a balanced out-of-the-box experience. Because of this, not all default settings prioritize fast response times. To learn how to achieve real-time responses from NPCs, see the recommendations (sorted by highest impact) below.

## 1. Choose a Fast LLM
For the best experience, you should aim to select an LLM provider / model that can return a response in less than 0.5 seconds. When a conversation is running, you can track how fast the LLM is responding via the Mantella window logs ("LLM took XYZ seconds to respond").

### a. Fast LLM Providers
Mantella is able to directly connect to many LLM providers, including those that excel in fast response times such as Cerebras and Groq. For more information on how to connect to such services, see <a href="./installation.html#other-llm-services">here</a>.  

### b. OpenRouter
#### Sort LLM Providers by Speed
Go to your [OpenRouter preferences](https://openrouter.ai/settings/preferences) and set "Default Provider Sort" to either "Latency" or "Throughput". Prioritizing latency will select the provider with the fastest response time. Prioritizing throughput will select the provider with the fastest tokens per second output.  

For real-time conversations, both fast response times (how long before the LLM starts generating a response) and high tokens per second (how long the LLM generates the first sentence) are important, so you will need find out which of the two works best for your chosen model.  

Note that changing your provider preferences to prioritize latency or throughput will consequently de-prioritize sorting by the lowest price.

#### Choose a Fast LLM
Once you have changed your preferences to either prioritize latency or throughput, you can view and select an OpenRouter model from the lists sorted by latency / throughput here:  
[https://openrouter.ai/models?order=latency-low-to-high](https://openrouter.ai/models?order=latency-low-to-high)  
[https://openrouter.ai/models?order=throughput-high-to-low](https://openrouter.ai/models?order=latency-low-to-high)  

### c. Local Models
If you have a high-end GPU, running LLMs locally has the advantage of eliminating network latency and providing consistent response times. For setup instructions on running local LLMs, see <a href="./installation.html##local-models">here</a>.

## 2. Disable Lip Sync
Set `Text-to-Speech`->`Lip File Generation` to "Lazy" in the Mantella UI. This reduces response times by about 0.5 seconds. See this setting's tooltip for more information.  

## 3. Enable Fast Response Mode
Enable `Text-to-Speech`->`Fast Response Mode` in the Mantella UI. This reduces response times by about 0.5 seconds. See this setting's tooltip for more information. Note that you can adjust the volume of these fast responses via the `Fast Response Mode Volume` setting.  

## 4. Adjust Microphone Settings
### Pause Threshold
Set `Speech-to-Text`->`Pause Threshold` as close to 0 as possible (without NPCs interrupting you!) in the Mantella UI.  

### Proactive Mic Transcriptions
Enable `Speech-to-Text`->`Proactive Mode` in the Mantella UI. This setting allows the chosen speech-to-text service to run at a constant frequency (determined by `Refresh Frequency`) from when speech starting is detected to when speech ending is detected. This streamlines the transcription process from the following pipeline:

> speech begins -> speech ends -> pause threshold is reached -> speech-to-text service triggers

to:

> speech begins -> speech-to-text service triggers at a constant interval -> speech ends -> pause threshold is reached

When configured correctly, this means the latency added by transcribing speech effectively becomes zero, as by the time the pause threshold has been reached, the speech-to-text service has already finished proactively transcribing the speech audio. For the best experience, ensure to set the value of `Refresh Frequency` to the lowest value your hardware can handle. This will take some tweaking to find the right value!  