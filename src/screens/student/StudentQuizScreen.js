import React,{useEffect,useMemo,useState} from 'react';
import {Alert,Pressable,ScrollView,Text,View,useWindowDimensions} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Header,Loading,ProgressBar} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

function Option({letter,text,selected,onPress,disabled}){
 return <Pressable disabled={disabled} onPress={onPress} style={({pressed})=>({flexDirection:'row',alignItems:'center',gap:11,borderWidth:1.5,borderColor:selected?colors.primary:colors.border,backgroundColor:selected?colors.blueSoft:'#fff',borderRadius:14,padding:13,marginBottom:9,opacity:pressed?.78:1})}>
   <View style={{width:34,height:34,borderRadius:10,alignItems:'center',justifyContent:'center',backgroundColor:selected?colors.primary:'#F8FAFC',borderWidth:1,borderColor:selected?colors.primary:colors.border}}><Text style={{fontWeight:'900',color:selected?'#fff':colors.navy}}>{letter}</Text></View>
   <Text style={{flex:1,fontSize:14,fontWeight:selected?'900':'700',color:colors.navy,lineHeight:20}}>{text}</Text>
   {selected&&<Text style={{fontSize:18,color:colors.primary}}>✓</Text>}
 </Pressable>;
}

export default function StudentQuizScreen({quizId,onBack}){
 const {width}=useWindowDimensions();
 const mobile=width<700;
 const [quiz,setQuiz]=useState(null),[questions,setQuestions]=useState([]),[answers,setAnswers]=useState({}),[attempt,setAttempt]=useState(null),[result,setResult]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const load=async()=>{try{setError('');const [q,qs]=await Promise.all([api.studentQuiz(quizId),api.quizQuestions(quizId)]);setQuiz(q);setQuestions(api.listOf(qs))}catch(e){setError(e?.message||'Unable to open this quiz.')}};
 useEffect(()=>{load()},[quizId]);
 const answered=useMemo(()=>Object.keys(answers).length,[answers]);
 const completion=questions.length?Math.round(answered/questions.length*100):0;
 if(error)return <AppShell><Header title="Quiz" right={<Button title="← Back" variant="secondary" onPress={onBack}/>}/><ErrorState title="Quiz could not load" message={error} onRetry={load}/></AppShell>;
 if(!quiz)return <AppShell><Loading label="Opening quiz…"/></AppShell>;
 const start=async()=>{setBusy(true);try{const a=await api.startQuiz(quizId);setAttempt(a)}catch(e){Alert.alert('Quiz',e.message)}finally{setBusy(false)}};
 const submit=async()=>{try{if(!attempt){Alert.alert('Quiz','Start the quiz first.');return}if(answered<questions.length){Alert.alert('Almost there',`Please answer all ${questions.length} questions before submitting.`);return}setBusy(true);const r=await api.submitQuiz(quizId,{attempt_id:attempt.attempt_id,answers});setResult(r)}catch(e){Alert.alert('Submit failed',e.message)}finally{setBusy(false)}};
 if(result)return <AppShell><View style={{maxWidth:720,width:'100%',alignSelf:'center'}}><Header eyebrow="Assessment complete" title="Quiz Result" subtitle={quiz.title||quiz.name} right={<Button title="← Back" variant="secondary" onPress={onBack}/>}/><Card style={{alignItems:'center',padding:mobile?22:34}}><View style={{width:88,height:88,borderRadius:44,backgroundColor:result.passed?colors.greenSoft:colors.orangeSoft,alignItems:'center',justifyContent:'center'}}><Text style={{fontSize:34}}>{result.passed?'🏆':'📚'}</Text></View><Text style={{fontSize:14,color:colors.muted,marginTop:15}}>Your score</Text><Text style={{fontSize:56,fontWeight:'900',color:colors.navy}}>{result.percentage}%</Text><Badge tone={result.passed?'green':'orange'}>{result.passed?'Passed':'Keep practicing'}</Badge><Text style={{marginTop:12,color:colors.muted}}>{result.correct_count} correct · {result.wrong_count} wrong</Text><ProgressBar value={result.percentage} color={result.passed?colors.success:colors.warning}/><Button title="Back to course" onPress={onBack} style={{marginTop:20,width:'100%'}}/></Card></View></AppShell>;
 return <AppShell><View style={{maxWidth:900,width:'100%',alignSelf:'center'}}>
   <Header eyebrow="Assessment" title={quiz.title||quiz.name||'Quiz'} subtitle={`${quiz.duration_minutes||15} minutes · Pass mark ${quiz.passing_percentage||60}%`} right={<Button title="← Back" variant="secondary" onPress={onBack}/>}/>
   {!attempt&&<Card style={{backgroundColor:colors.navy,borderColor:colors.navy,padding:mobile?18:24}}><View style={{flexDirection:'row',alignItems:'center',gap:14}}><View style={{width:52,height:52,borderRadius:15,backgroundColor:'rgba(255,255,255,.10)',alignItems:'center',justifyContent:'center'}}><Text style={{fontSize:24}}>📝</Text></View><View style={{flex:1}}><Text style={{fontSize:20,fontWeight:'900',color:'#fff'}}>Ready to test your knowledge?</Text><Text style={{color:'#CBD5E1',marginTop:5,lineHeight:19}}>{questions.length} questions · {quiz.duration_minutes||15} minutes · Pass at {quiz.passing_percentage||60}%</Text></View></View><View style={{flexDirection:'row',flexWrap:'wrap',gap:8,marginTop:18}}><Badge tone="pink">{questions.length} Questions</Badge><Badge tone="purple">{quiz.passing_percentage||60}% Pass</Badge><Badge tone="orange">Timed</Badge></View><Button title={busy?'Starting…':'Start Quiz'} onPress={start} disabled={busy} style={{marginTop:18}}/></Card>}
   {attempt&&<>
    <Card style={{padding:15}}><View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginBottom:8}}><Text style={{fontWeight:'900',color:colors.navy}}>Your progress</Text><Text style={{fontWeight:'900',color:colors.primary}}>{answered}/{questions.length}</Text></View><ProgressBar value={completion}/><Text style={{fontSize:11,color:colors.muted,marginTop:6}}>{completion}% answered · Review your choices before submitting.</Text></Card>
    {questions.length===0?<Empty title="No questions found" message="This quiz has no published questions yet."/>:questions.map((q,i)=>{const qid=api.idOf(q);return <Card key={qid} style={{padding:mobile?14:20}}><View style={{flexDirection:'row',justifyContent:'space-between',gap:10}}><Badge tone="purple">Question {i+1}</Badge><Text style={{fontSize:11,color:colors.muted}}>{i+1} / {questions.length}</Text></View><Text style={{fontSize:mobile?17:19,fontWeight:'900',color:colors.navy,lineHeight:25,marginTop:12}}>{q.question}</Text><View style={{marginTop:14}}>{(q.options||[]).map((o,oi)=>{const label=typeof o==='object'?(o.text||o.label||o.value||'Option'):String(o);return <Option key={oi} letter={String.fromCharCode(65+oi)} text={label} selected={String(answers[qid])===String(oi)} onPress={()=>setAnswers(prev=>({...prev,[qid]:oi}))}/>})}</View></Card>})}
    {questions.length>0&&<Card style={{backgroundColor:'#fff',borderColor:colors.primary,borderWidth:1.5}}><View style={{flexDirection:mobile?'column':'row',alignItems:mobile?'stretch':'center',justifyContent:'space-between',gap:12}}><View><Text style={{fontWeight:'900',color:colors.navy}}>Ready to finish?</Text><Text style={{fontSize:12,color:colors.muted,marginTop:3}}>{answered} of {questions.length} answered</Text></View><Button title={busy?'Submitting…':'Submit Quiz'} onPress={submit} disabled={busy||answered<questions.length}/></View></Card>}
   </>}
 </View></AppShell>;
}
