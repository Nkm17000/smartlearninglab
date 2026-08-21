import React,{useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Button,Card,Field,Header,Select,Badge} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function AdminAILabScreen(){
 const [tab,setTab]=useState('course');
 const [title,setTitle]=useState('English Spoken Mastery');
 const [description,setDescription]=useState('Practical spoken English for beginners and working professionals.');
 const [level,setLevel]=useState('Beginner'); const [days,setDays]=useState('30'); const [topic,setTopic]=useState('Spoken English');
 const [count,setCount]=useState('10'); const [difficulty,setDifficulty]=useState('medium');
 const [result,setResult]=useState(null); const [busy,setBusy]=useState(false);
 const generateCourse=async()=>{setBusy(true);try{setResult(await api.aiGenerateCourse({title,description,level,duration_days:Number(days)}))}catch(e){Alert.alert('AI Course Generator',e.message)}finally{setBusy(false)}};
 const generateQuiz=async()=>{setBusy(true);try{setResult(await api.aiGenerateQuiz({topic,count:Number(count),difficulty,title:`${topic} Practice Test`}))}catch(e){Alert.alert('AI Quiz Generator',e.message)}finally{setBusy(false)}};
 const saveCourse=async()=>{try{const r=await api.aiSaveCourse({title,description,level,duration_days:Number(days)});Alert.alert('Course created',`Draft course ${r.course_id} is ready in Course Builder.`)}catch(e){Alert.alert('Save course',e.message)}};
 const saveQuiz=async()=>{try{const r=await api.aiSaveQuiz({topic,count:Number(count),difficulty,title:`${topic} Practice Test`});Alert.alert('Quiz created',`Draft quiz ${r.quiz_id} and ${r.question_ids.length} questions created.`)}catch(e){Alert.alert('Save quiz',e.message)}};
 return <AppShell><Header eyebrow="Admin AI Lab" title="Create content faster" subtitle="Generate complete course structures and question sets, review them, then publish from the normal admin workflow."/>
  <View style={{flexDirection:'row',flexWrap:'wrap',gap:8,marginBottom:14}}><Button title="AI Course Generator" variant={tab==='course'?'primary':'secondary'} onPress={()=>{setTab('course');setResult(null)}}/><Button title="AI Quiz Generator" variant={tab==='quiz'?'primary':'secondary'} onPress={()=>{setTab('quiz');setResult(null)}}/></View>
  {tab==='course'?<Card><Badge tone="purple">Course Generator</Badge><Field label="Course title" value={title} onChangeText={setTitle}/><Field label="Course description" value={description} onChangeText={setDescription} multiline/><Select label="Level" value={level} onChange={setLevel} options={['Beginner','Intermediate','Advanced'].map(x=>({label:x,value:x}))}/><Field label="Duration (days)" value={days} onChangeText={setDays} keyboardType="numeric"/><View style={{flexDirection:'row',gap:10,flexWrap:'wrap'}}><Button title={busy?'Generating...':'✨ Generate Course'} onPress={generateCourse} disabled={busy}/><Button title="Generate & Save Draft" variant="secondary" onPress={saveCourse} disabled={busy}/></View></Card>
  :<Card><Badge tone="purple">Quiz Generator</Badge><Field label="Topic" value={topic} onChangeText={setTopic}/><Field label="Number of questions" value={count} onChangeText={setCount} keyboardType="numeric"/><Select label="Difficulty" value={difficulty} onChange={setDifficulty} options={['easy','medium','hard'].map(x=>({label:x,value:x}))}/><View style={{flexDirection:'row',gap:10,flexWrap:'wrap'}}><Button title={busy?'Generating...':'✨ Generate Questions'} onPress={generateQuiz} disabled={busy}/><Button title="Generate & Save Draft" variant="secondary" onPress={saveQuiz} disabled={busy}/></View></Card>}
  {result&&<Card><Text style={{fontSize:20,fontWeight:'900',color:colors.navy}}>Generated Preview</Text><Text style={{color:colors.muted,marginTop:6}}>Review the draft before publishing.</Text>{result.course?<><Text style={{fontWeight:'900',marginTop:16}}>{result.course.title}</Text>{result.course.modules?.map((m,i)=><View key={i} style={{marginTop:10,padding:12,backgroundColor:'#F8FAFC',borderRadius:12}}><Text style={{fontWeight:'900'}}>{i+1}. {m.title}</Text><Text style={{color:colors.muted,marginTop:4}}>{m.lessons.length} lessons</Text></View>)}</>:result.quiz?<><Text style={{fontWeight:'900',marginTop:16}}>{result.quiz.title}</Text>{result.quiz.questions?.slice(0,5).map((q,i)=><View key={i} style={{marginTop:10,padding:12,backgroundColor:'#F8FAFC',borderRadius:12}}><Text style={{fontWeight:'800'}}>{i+1}. {q.question}</Text><Text style={{color:colors.muted,marginTop:4}}>{q.options.join(' • ')}</Text></View>)}<Text style={{color:colors.muted,marginTop:10}}>Showing first 5 questions in preview.</Text></>:null}</Card>}
 </AppShell>
}
