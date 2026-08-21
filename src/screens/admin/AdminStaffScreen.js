import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Field,Header,Loading,Select} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function AdminStaffScreen(){
 const [items,setItems]=useState(null),[show,setShow]=useState(false),[name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[role,setRole]=useState('admin'),[error,setError]=useState('');
 const load=async()=>{try{setError('');setItems(api.listOf(await api.adminList()))}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 const create=async()=>{try{await api.adminCreate({name,email,password,role});setName('');setEmail('');setPassword('');setShow(false);load()}catch(e){Alert.alert('Create admin',e.message)}};
 const toggle=async x=>{try{await api.adminStatus(api.idOf(x),!x.is_active);load()}catch(e){Alert.alert('Staff',e.message)}};
 const remove=async x=>{try{await api.adminDelete(api.idOf(x));load()}catch(e){Alert.alert('Staff',e.message)}};
 if(error)return <AppShell><Header title="Admin & Staff"/><ErrorState title="Staff could not load" message={error} onRetry={load}/></AppShell>;
 if(!items)return <AppShell><Loading label="Loading staff…"/></AppShell>;
 return <AppShell><Header eyebrow="Root admin" title="Admin & Staff" subtitle="Create and manage role-based staff accounts." right={<Button title={show?'Close':'+ Create Admin'} onPress={()=>setShow(!show)}/>}/>
 {show&&<Card><Text style={{fontSize:19,fontWeight:'900',marginBottom:12}}>Create staff account</Text><Field label="Name" value={name} onChangeText={setName}/><Field label="Email" value={email} onChangeText={setEmail} keyboardType="email-address"/><Field label="Temporary password" value={password} onChangeText={setPassword} secureTextEntry/><Select label="Role" value={role} onChange={setRole} options={[{label:'Admin',value:'admin'},{label:'Content Admin',value:'content_admin'},{label:'Instructor',value:'instructor'},{label:'Support Admin',value:'support_admin'}]}/><Button title="Create staff" onPress={create} disabled={!name||!email||password.length<8}/></Card>}
 {items.map(x=><Card key={api.idOf(x)}><View style={{flexDirection:'row',alignItems:'center',gap:12}}><View style={{flex:1}}><Text style={{fontWeight:'900',color:colors.navy}}>{x.name}</Text><Text style={{fontSize:12,color:colors.muted,marginTop:3}}>{x.email}</Text></View><Badge tone="purple">{x.role}</Badge><Button title={x.is_active?'Disable':'Enable'} variant="secondary" onPress={()=>toggle(x)}/><Button title="Delete" variant="danger" onPress={()=>remove(x)}/></View></Card>)}
 </AppShell>;
}
