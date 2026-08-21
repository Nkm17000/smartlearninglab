import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Field,Header,Loading,Select} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

const blank={question:'',options:['','','',''],correct_answer:0,difficulty:'easy',marks:'1',negative_marks:'0',explanation:''};

function NewQuestion({onSave,onCancel}){
 const [f,setF]=useState(blank),[busy,setBusy]=useState(false);
 const save=async()=>{setBusy(true);try{await onSave({...f,marks:Number(f.marks)||1,negative_marks:Number(f.negative_marks)||0})}catch(e){Alert.alert('Question',e.message)}finally{setBusy(false)}};
 return <Card style={{marginTop:12,backgroundColor:'#F8FAFC',borderStyle:'dashed'}}>
  <Text style={{fontSize:17,fontWeight:'900',color:colors.navy,marginBottom:10}}>New question for this quiz</Text>
  <Field label="Question" value={f.question} onChangeText={v=>setF({...f,question:v})} multiline/>
  {f.options.map((x,i)=><Field key={i} label={`Option ${String.fromCharCode(65+i)}`} value={x} onChangeText={v=>{const a=[...f.options];a[i]=v;setF({...f,options:a})}}/>)}
  <Select label="Correct answer" value={f.correct_answer} onChange={v=>setF({...f,correct_answer:v})} options={[0,1,2,3].map(i=>({value:i,label:`Option ${String.fromCharCode(65+i)}`}))}/>
  <Select label="Difficulty" value={f.difficulty} onChange={v=>setF({...f,difficulty:v})} options={[{value:'easy',label:'Easy'},{value:'medium',label:'Medium'},{value:'hard',label:'Hard'}]}/>
  <Field label="Explanation" value={f.explanation} onChangeText={v=>setF({...f,explanation:v})} multiline/>
  <View style={{flexDirection:'row',gap:8}}><Button title={busy?'Saving…':'Create & Add'} onPress={save} disabled={busy||!f.question.trim()||f.options.some(x=>!x.trim())}/><Button title="Cancel" variant="secondary" onPress={onCancel}/></View>
 </Card>
}

function ExistingPicker({quiz,onAdd}){
 const [open,setOpen]=useState(false),[items,setItems]=useState([]);
 const load=async()=>{const all=api.listOf(await api.questions());const used=(quiz.question_ids||[]).map(String);setItems(all.filter(q=>!used.includes(api.idOf(q))))};
 if(!open)return <Button title="+ Existing Question" variant="secondary" onPress={()=>{load();setOpen(true)}}/>;
 return <Card style={{marginTop:12,backgroundColor:'#fff'}}>
  <View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center'}}><Text style={{fontWeight:'900'}}>Question bank</Text><Button title="Close" variant="secondary" onPress={()=>setOpen(false)}/></View>
  {items.length===0?<Text style={{color:colors.muted,marginTop:8}}>No unused questions.</Text>:items.map(q=><View key={api.idOf(q)} style={{flexDirection:'row',alignItems:'center',gap:8,paddingVertical:8,borderTopWidth:1,borderTopColor:colors.border}}><Text style={{flex:1}} numberOfLines={2}>{q.question}</Text><Button title="Add" onPress={()=>{onAdd(api.idOf(q));setOpen(false)}}/></View>)}
 </Card>
}

function QuizEditor({quiz,onReload}){
 const [showNew,setShowNew]=useState(false),[title,setTitle]=useState(quiz.title||quiz.name||''),[duration,setDuration]=useState(String(quiz.duration_minutes||15)),[passing,setPassing]=useState(String(quiz.passing_percentage||60)),[saving,setSaving]=useState(false);
 const save=async()=>{try{setSaving(true);await api.updateQuiz(api.idOf(quiz),{title,name:title,duration_minutes:Number(duration)||15,passing_percentage:Number(passing)||60});onReload()}catch(e){Alert.alert('Quiz',e.message)}finally{setSaving(false)}};
 const add=async id=>{try{await api.addQuizQuestions(api.idOf(quiz),[id]);onReload()}catch(e){Alert.alert('Question',e.message)}};
 const remove=async id=>{try{await api.removeQuizQuestion(api.idOf(quiz),id);onReload()}catch(e){Alert.alert('Question',e.message)}};
 const create=async d=>{await api.createQuizQuestion(api.idOf(quiz),d);setShowNew(false);onReload()};
 const [questions,setQuestions]=useState([]);
 useEffect(()=>{api.questions().then(x=>{const all=api.listOf(x);const ids=(quiz.question_ids||[]).map(String);setQuestions(all.filter(q=>ids.includes(api.idOf(q))))}).catch(()=>{})},[quiz.question_ids?.length]);
 return <Card style={{marginTop:12,backgroundColor:'#F8FAFC'}}>
  <View style={{flexDirection:'row',alignItems:'center',gap:10}}><Text style={{fontSize:24}}>📝</Text><View style={{flex:1}}><Text style={{fontSize:18,fontWeight:'900',color:colors.navy}}>{quiz.title||quiz.name}</Text><Text style={{color:colors.muted}}>{(quiz.question_ids||[]).length} questions</Text></View><Badge tone={quiz.is_published?'green':'orange'}>{quiz.is_published?'Published':'Draft'}</Badge></View>
  <View style={{marginTop:12}}><Field label="Quiz title" value={title} onChangeText={setTitle}/><View style={{flexDirection:'row',gap:10,flexWrap:'wrap'}}><View style={{flex:1,minWidth:180}}><Field label="Duration (minutes)" value={duration} onChangeText={setDuration} keyboardType="numeric"/></View><View style={{flex:1,minWidth:180}}><Field label="Passing score (%)" value={passing} onChangeText={setPassing} keyboardType="numeric"/></View></View><View style={{flexDirection:'row',gap:8,flexWrap:'wrap'}}><Button title={saving?'Saving…':'Save Quiz'} onPress={save} disabled={saving||!title.trim()}/><Button title={quiz.is_published?'Unpublish':'Publish'} variant="secondary" onPress={async()=>{try{quiz.is_published?await api.unpublishQuiz(api.idOf(quiz)):await api.publishQuiz(api.idOf(quiz));onReload()}catch(e){Alert.alert('Publish',e.message)}}}/><Button title="Delete" variant="danger" onPress={async()=>{try{await api.deleteQuiz(api.idOf(quiz));onReload()}catch(e){Alert.alert('Delete',e.message)}}}/></View></View>
  <Text style={{fontWeight:'900',fontSize:16,color:colors.navy,marginTop:15}}>Questions in quiz</Text>
  {questions.length===0?<Text style={{color:colors.muted,marginTop:7}}>No questions yet. Add one below.</Text>:questions.map((q,i)=><View key={api.idOf(q)} style={{flexDirection:'row',alignItems:'center',paddingVertical:9,borderTopWidth:1,borderTopColor:colors.border}}><View style={{flex:1}}><Text style={{fontWeight:'800'}}>{i+1}. {q.question}</Text><Text style={{fontSize:12,color:colors.muted}}>{q.difficulty||'easy'}</Text></View><Button title="Remove" variant="danger" onPress={()=>remove(api.idOf(q))}/></View>)}
  <View style={{flexDirection:'row',gap:8,flexWrap:'wrap',marginTop:12}}><Button title="+ New Question" onPress={()=>setShowNew(!showNew)}/><ExistingPicker quiz={quiz} onAdd={add}/></View>
  {showNew&&<NewQuestion onSave={create} onCancel={()=>setShowNew(false)}/>}
 </Card>
}

export default function AdminQuizzesScreen(){
 const [items,setItems]=useState(null),[error,setError]=useState(''),[showCreate,setShowCreate]=useState(false);
 const [title,setTitle]=useState(''),[description,setDescription]=useState(''),[duration,setDuration]=useState('15'),[passing,setPassing]=useState('60');

 const load=()=>{
   setError('');
   api.quizzes()
     .then(x=>setItems(api.listOf(x)))
     .catch(e=>setError(e.message));
 };

 useEffect(()=>{load()},[]);

 const create=async()=>{
   try{
     await api.createQuiz({
       title,
       name:title,
       description,
       course_id:null,
       module_id:null,
       duration_minutes:Number(duration)||15,
       passing_percentage:Number(passing)||60,
       max_attempts:3,
       question_ids:[],
       is_published:false
     });
     setTitle('');
     setDescription('');
     setShowCreate(false);
     load();
   }catch(e){
     Alert.alert('Quiz',e.message);
   }
 };

 if(error){
   return (
     <AppShell>
       <Header
         title="Quizzes"
         subtitle="Create quizzes and build their question sets."
       />
       <ErrorState
         title="Quizzes could not load"
         message={error}
         onRetry={load}
       />
     </AppShell>
   );
 }

 return (
   <AppShell>
     <Header
       eyebrow="Admin"
       title="Quizzes"
       subtitle="Create a quiz, then add existing or brand-new questions inside it."
       right={
         <Button
           title={showCreate ? 'Close' : '+ New Quiz'}
           onPress={()=>setShowCreate(!showCreate)}
         />
       }
     />

     {showCreate && (
       <Card>
         <Text style={{fontSize:19,fontWeight:'900',marginBottom:12}}>
           Create quiz
         </Text>

         <Field
           label="Quiz title"
           value={title}
           onChangeText={setTitle}
           placeholder="English Foundations Quiz"
         />

         <Field
           label="Description"
           value={description}
           onChangeText={setDescription}
           multiline
         />

         <View style={{flexDirection:'row',gap:10,flexWrap:'wrap'}}>
           <View style={{flex:1,minWidth:180}}>
             <Field
               label="Duration"
               value={duration}
               onChangeText={setDuration}
               keyboardType="numeric"
             />
           </View>

           <View style={{flex:1,minWidth:180}}>
             <Field
               label="Passing %"
               value={passing}
               onChangeText={setPassing}
               keyboardType="numeric"
             />
           </View>
         </View>

         <Button
           title="Create Quiz"
           onPress={create}
           disabled={!title.trim()}
         />
       </Card>
     )}

     {!items ? (
       <Loading label="Loading quizzes…" />
     ) : items.length === 0 ? (
       <Empty
         title="No quizzes yet"
         message="Create your first quiz."
       />
     ) : (
       items.map(q => (
         <QuizEditor
           key={api.idOf(q)}
           quiz={q}
           onReload={load}
         />
       ))
     )}
   </AppShell>
 );
}
