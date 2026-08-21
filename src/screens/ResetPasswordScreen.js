import React,{useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Button,Card,Field} from '../components/UI';
import {api} from '../services/api';
import {colors} from '../theme';

export default function ResetPasswordScreen({token,onDone}){
 const [password,setPassword]=useState('');const [confirm,setConfirm]=useState('');const [busy,setBusy]=useState(false);
 const submit=async()=>{if(password.length<8)return Alert.alert('Password','Use at least 8 characters.');if(password!==confirm)return Alert.alert('Password','Passwords do not match.');try{setBusy(true);await api.resetPassword(token,password);Alert.alert('Password reset','Your password has been changed.');onDone()}catch(e){Alert.alert('Password reset',e.message)}finally{setBusy(false)}};
 return <AppShell><View style={{maxWidth:500,width:'100%',alignSelf:'center',marginTop:55}}><Text style={{fontSize:34,fontWeight:'900',color:colors.navy}}>Reset your password</Text><Text style={{color:colors.muted,marginTop:6,marginBottom:20}}>Choose a new password for your Smart Learning Lab account.</Text><Card><Field label="New password" value={password} onChangeText={setPassword} secureTextEntry/><Field label="Confirm password" value={confirm} onChangeText={setConfirm} secureTextEntry/><Button title={busy?'Updating…':'Update password'} onPress={submit} disabled={busy||!password||!confirm}/><View style={{marginTop:12}}><Button title="Back to sign in" variant="secondary" onPress={onDone}/></View></Card></View></AppShell>;
}
