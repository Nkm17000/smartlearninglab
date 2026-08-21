import React,{useState} from 'react';
import {Alert,Text,TextInput,View} from 'react-native';
import {AppShell,Button,Card,Header} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';
export default function StudentSpeakingScreen(){
 const [target,setTarget]=useState('Tell me about yourself and your daily routine.');
 const [transcript,setTranscript]=useState(''); const [result,setResult]=useState(null); const [busy,setBusy]=useState(false);
 const evaluate=async()=>{if(!transcript.trim())return Alert.alert('Speaking practice','Enter what you said first.');setBusy(true);try{setResult(await api.evaluateSpeaking({target_text:target,transcript}));}catch(e){Alert.alert('Speaking practice',e.message)}finally{setBusy(false)}};
 return <AppShell><Header eyebrow="Practice" title="AI Speaking Practice" subtitle="Practice an answer, then get instant feedback on fluency, grammar and vocabulary."/>
  <Card><Text style={{fontWeight:'900',fontSize:17,color:colors.navy,marginBottom:8}}>Prompt</Text><TextInput value={target} onChangeText={setTarget} multiline style={{borderWidth:1,borderColor:colors.border,borderRadius:12,padding:12,color:colors.text,minHeight:70,backgroundColor:'#fff'}}/>
  <Text style={{fontWeight:'900',fontSize:17,color:colors.navy,marginTop:18,marginBottom:8}}>Your answer / transcript</Text><TextInput value={transcript} onChangeText={setTranscript} multiline placeholder="Type what you said after speaking..." style={{borderWidth:1,borderColor:colors.border,borderRadius:12,padding:12,color:colors.text,minHeight:130,backgroundColor:'#fff'}}/>
  <View style={{marginTop:12}}><Button title={busy?'Evaluating...':'Evaluate my speaking'} onPress={evaluate} disabled={busy||!transcript.trim()}/></View></Card>
  {result&&<Card><Text style={{fontSize:22,fontWeight:'900',color:colors.navy}}>Overall {result.scores.overall}%</Text><View style={{flexDirection:'row',flexWrap:'wrap',gap:10,marginTop:14}}>{Object.entries(result.scores).filter(([k])=>k!=='overall').map(([k,v])=><View key={k} style={{padding:12,borderRadius:12,backgroundColor:'#F8FAFC',minWidth:120}}><Text style={{fontWeight:'800',color:colors.muted}}>{k}</Text><Text style={{fontSize:20,fontWeight:'900',color:colors.primary}}>{v}%</Text></View>)}</View><Text style={{fontWeight:'900',marginTop:16,color:colors.navy}}>Suggestions</Text>{(result.feedback||result.suggestions||[]).map((x,i)=><Text key={i} style={{marginTop:7,color:colors.text}}>• {x}</Text>)}</Card>}
 </AppShell>;
}
